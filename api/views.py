import os
import hashlib
import traceback
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from passlib.context import CryptContext
from .models import Client, GamingTable, DailyGameSession, Order, CafeTableOccupation, Menu, Waiter, FinancialRecord, GameType, Admin, SessionConfig

# Use pbkdf2_sha256 to be consistent and avoid bcrypt limits
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def check_admin_role(request, required_level="super_admin"):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ")[1]
    if not token.startswith("token-"):
        return False
    parts = token.split("-")
    if len(parts) < 3:
        return False
    
    admin_id = parts[1]
    try:
        admin = Admin.objects.get(id=admin_id)
        if required_level == "super_admin":
            return admin.admin_level == "super_admin"
        return admin.admin_level in ["super_admin", "simple_admin"]
    except Admin.DoesNotExist:
        return False



@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Manual login with phone and password."""
    data = request.data
    phone = data.get('phone')
    password = data.get('password')
    
    if phone:
        phone = phone.strip()

    if not phone or not password:
        return Response({"detail": "Phone and password required"}, status=status.HTTP_400_BAD_REQUEST)
        
    # Block admin credentials from being used on the member login page.
    # Admins must use the dedicated /sys-admin/login endpoint instead.
    admin_account = Admin.objects.filter(username__iexact=phone).first()
    if admin_account:
        return Response({"detail": "Admin accounts cannot log in here. Please use the admin panel."}, status=status.HTTP_403_FORBIDDEN)

    try:
        # Multi-identifier login: username (full_name_cl), phone, or email
        user = Client.objects.filter(
            Q(full_name_cl__iexact=phone) | 
            Q(phone_cl__iexact=phone) | 
            Q(email_cl__iexact=phone)
        ).first()
        
        if not user:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            
        # Verify password
        pw_to_check = hashlib.sha256(password.encode('utf-8')).hexdigest()
        
        is_valid = False
        if user.password_hash:
            try:
                is_valid = pwd_context.verify(pw_to_check, user.password_hash)
            except Exception:
                pass
            
            # Fallback for plain text or pure SHA-256 legacy hashes
            if not is_valid and (user.password_hash == pw_to_check or user.password_hash == password):
                is_valid = True
                
        if not is_valid:
            return Response({"detail": "Incorrect password"}, status=status.HTTP_401_UNAUTHORIZED)
            
        # Include session config for user session management
        config = SessionConfig.get_config()
        return Response({
            "status": "success",
            "id": user.id,
            "user": user.full_name_cl,
            "login_timestamp": timezone.now().isoformat(),
            "session_duration_hours": config.user_session_hours
        })
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
@permission_classes([AllowAny])
def guest_login(request):
    """Allows a guest to 'sign in' with just a name."""
    full_name = request.data.get('full_name')
    if not full_name:
        return Response({"detail": "Full name is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create a basic client record
        client = Client.objects.create(full_name_cl=full_name)
        return Response({
            "status": "success",
            "id": client.id,
            "name": client.full_name_cl,
            "is_guest": True
        })
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    data = request.data
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    phone = data.get('phone')
    email = data.get('email')
    password = data.get('password')
    photo = request.FILES.get('photo')

    if phone:
        phone = phone.strip()
    if email:
        email = email.strip()

    print(f"DEBUG: Signup request received for phone: {phone}")
    print(f"DEBUG: Photo present: {photo is not None}")

    if not all([first_name, last_name, phone, password]):
        return Response({"detail": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

    file_path = None
    if photo:
        upload_dir = os.path.join(settings.BASE_DIR, "uploads/user_photos")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, photo.name)
        
        with open(file_path, "wb") as buffer:
            for chunk in photo.chunks():
                buffer.write(chunk)
            
    try:
        # 1. Hashing Logic: Match legacy FastAPI logic (SHA256 pre-hash)
        import hashlib
        pw_to_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        password_hash = pwd_context.hash(pw_to_hash)
        
        # 2. Check for existing
        existing_phone = Client.objects.filter(phone_cl=phone).first()
        if existing_phone:
            print(f"DEBUG: Signup failed. Phone '{phone}' already exists for user '{existing_phone.full_name_cl}' (ID: {existing_phone.id})")
            return Response({"detail": "This phone number is already registered. Please log in instead."}, status=status.HTTP_400_BAD_REQUEST)
            
        # 3. Create
        new_client = Client.objects.create(
            full_name_cl=f"{first_name} {last_name}",
            phone_cl=phone,
            email_cl=email,
            password_hash=password_hash,
            image_path=file_path
        )
        print(f"DEBUG: Successfully created new client: {new_client.full_name_cl} (ID: {new_client.id})")
        return Response({"status": "success", "id": new_client.id, "message": "User registered successfully"})
    except Exception as e:
        print(f"Signup error: {traceback.format_exc()}")
        return Response({"detail": f"Internal server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ... existing views ...

@api_view(['GET'])
def get_game_status(request):
    """Returns the list of tables and the players currently in line for each."""
    tables = GamingTable.objects.select_related('game_type').all()
    today = timezone.now().date()
    now = timezone.now()
    
    # Heartbeat update for connected client
    client_id = request.query_params.get('client_id')
    if client_id:
        try:
            Client.objects.filter(id=client_id).update(last_seen_at=now)
        except Exception as e:
            print("Heartbeat update failed:", e)

    # Process timeouts and next-in-line for each table
    for table in tables:
        # 1. Check for timeout on notified players
        notified_player = DailyGameSession.objects.filter(
            game_table=table, 
            status='notified',
            game_status='active',
            created_at__date=today
        ).first()
        
        if notified_player and notified_player.notified_at:
            # Handle naive vs aware datetimes
            player_notified_at = notified_player.notified_at
            if timezone.is_naive(player_notified_at):
                player_notified_at = timezone.make_aware(player_notified_at)
            
            elapsed = (now - player_notified_at).total_seconds()
            if elapsed > 60: # 1 minute timeout
                notified_player.status = 'cancelled'
                notified_player.game_status = 'active' # Keep active for traceability
                notified_player.save()
                notified_player = None 
        
        # 2. Check if table is free and needs a new notified player
        # A table is "occupied" if someone is 'playing'
        is_occupied = DailyGameSession.objects.filter(
            game_table=table, 
            status='playing',
            created_at__date=today
        ).exists()
        
        if not is_occupied and not notified_player:
            # Table is free, notify the next person in line
            next_in_line = DailyGameSession.objects.filter(
                game_table=table,
                status='waiting',
                game_status='active',
                created_at__date=today
            ).order_by('daily_number').first()
            
            if next_in_line:
                next_in_line.status = 'notified'
                next_in_line.notified_at = now
                next_in_line.save()

        # 3. Check for timeout on playing players (20 minutes)
        playing_player = DailyGameSession.objects.filter(
            game_table=table, 
            status='playing',
            game_status='active',
            created_at__date=today
        ).first()

        if playing_player and playing_player.notified_at:
            player_playing_at = playing_player.notified_at
            if timezone.is_naive(player_playing_at):
                player_playing_at = timezone.make_aware(player_playing_at)
            
            elapsed_playing = (now - player_playing_at).total_seconds()
            if elapsed_playing > 1200: # 20 minutes timeout
                playing_player.status = 'completed'
                playing_player.game_status = 'active'
                playing_player.save()

    # 4. Filter sessions for display: active on top, history only for last 2 hours
    two_hours_ago = now - timedelta(hours=2)
    
    # Active sessions (waiting, notified, playing)
    active_sessions_qs = DailyGameSession.objects.filter(
        created_at__date=today,
        status__in=['waiting', 'notified', 'playing'],
        game_status='active'
    )
    
    # Recent history (completed, cancelled) within last 2 hours
    history_sessions_qs = DailyGameSession.objects.filter(
        created_at__date=today,
        status__in=['completed', 'cancelled'],
        game_status='active',
        created_at__gte=two_hours_ago
    )
    
    from django.db.models import Q
    active_sessions = DailyGameSession.objects.filter(
        Q(status__in=['waiting', 'notified', 'playing']) |
        (Q(status__in=['completed', 'cancelled']) & Q(created_at__gte=two_hours_ago)),
        created_at__date=today,
        game_status='active'
    ).select_related('client', 'game_table').order_by('daily_number')
    
    # Prefetch history for these clients
    client_ids = [s.client_id for s in active_sessions]
    
    # 1. Games played counts for today
    sessions_count = DailyGameSession.objects.filter(
        client_id__in=client_ids,
        status='completed',
        created_at__date=today
    ).values('client_id').annotate(count=Count('session_id'))
    session_count_map = {item['client_id']: item['count'] for item in sessions_count}

    # 2. Recent orders
    orders = Order.objects.filter(client_id__in=client_ids).order_by('-created_at')
    orders_map = {}
    for cmd in orders:
        if cmd.client_id not in orders_map:
            orders_map[cmd.client_id] = []
        if len(orders_map[cmd.client_id]) < 3: # Limit to 3 recent
            orders_map[cmd.client_id].append({
                "name": cmd.name_order,
                "status": cmd.status,
                "table": cmd.cafe_table_number if cmd.cafe_table_number else (cmd.game_table.gamet_name if cmd.game_table else "General"),
                "waiter": cmd.waiter.full_name if cmd.waiter else "Unassigned"
            })

    table_data = []
    for table in tables:
        players = []
        for s in active_sessions:
            if s.game_table_id == table.id_gamet:
                timer = 0
                if s.status == 'notified' and s.notified_at:
                    s_notified_at = s.notified_at
                    if timezone.is_naive(s_notified_at):
                        s_notified_at = timezone.make_aware(s_notified_at)
                    timer = max(0, 60 - int((now - s_notified_at).total_seconds()))
                
                players.append({
                    "id": s.client.id,
                    "session_id": s.session_id,
                    "name": s.client.full_name_cl,
                    "daily_number": s.daily_number,
                    "status": s.status,
                    "timer": timer,
                    "games_played_today": session_count_map.get(s.client_id, 0),
                    "recent_orders": orders_map.get(s.client_id, [])
                })
        
        # Use a more explicit lookup for the linter and safety
        gt = getattr(table, 'game_type', None)
        table_data.append({
            "id": table.id_gamet,
            "name": table.gamet_name,
            "number": table.gamet_number,
            "location": table.gamet_club,
            "game_type": gt.name if gt else "General",
            "game_image": gt.image_path if gt else None,
            "players": players
        })
    
    return Response(table_data)

@api_view(['POST'])
def join_game(request):
    """Adds a client to the daily_game_session for a specific table."""
    client_id = request.data.get('client_id')
    table_id = request.data.get('table_id')
    
    if not client_id or not table_id:
        return Response({"detail": "Missing client_id or table_id"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        client = Client.objects.get(id=client_id)
        table = GamingTable.objects.get(id_gamet=table_id)
        
        # Prevent multiple active sessions for the same user
        active_today = DailyGameSession.objects.filter(
            client=client,
            game_status='active',
            status__in=['waiting', 'notified', 'playing'],
            created_at__date=timezone.now().date()
        ).exists()
        
        if active_today:
            return Response({"detail": "You are already in a queue or playing at another table."}, status=status.HTTP_400_BAD_REQUEST)

        # Calculate daily number (could be incremental for the day or specific to table)
        today = timezone.now().date()
        daily_count = DailyGameSession.objects.filter(created_at__date=today, game_table=table).count()
        
        new_session = DailyGameSession.objects.create(
            client=client,
            game_table=table,
            daily_number=daily_count + 1,
            game_status='active',
            created_at=timezone.now()
        )
        
        return Response({
            "status": "success",
            "message": f"Joined table {table.gamet_name}",
            "daily_number": new_session.daily_number
        })
    except Client.DoesNotExist:
        return Response({"detail": "Client not found"}, status=status.HTTP_404_NOT_FOUND)
    except GamingTable.DoesNotExist:
        return Response({"detail": "Table not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['POST'])
def place_order(request):
    """Saves an order to the database."""
    client_id = request.data.get('client_id')
    item_name = request.data.get('item_name')
    price = request.data.get('price')
    table_id = request.data.get('table_id') # Gaming table
    cafe_table_number = request.data.get('cafe_table_number') # Cafe table
    
    if not client_id or not item_name or not price:
        return Response({"detail": "Missing ordering info"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        client = Client.objects.get(id=client_id)
        table = None
        if table_id:
            table = GamingTable.objects.get(id_gamet=table_id)
            
        # Automatic Waiter Repartition Logic
        assigned_waiter = None
        # Try to find the active waiter with the lowest load
        active_waiters = Waiter.objects.filter(status='active').order_by('current_load')
        if active_waiters.exists():
            assigned_waiter = active_waiters.first()
            assigned_waiter.current_load += 1
            assigned_waiter.save()

        new_order = Order.objects.create(
            name_order=item_name,
            price=price,
            client=client,
            game_table=table,
            cafe_table_number=cafe_table_number,
            waiter=assigned_waiter,
            created_at=timezone.now()
        )
        
        return Response({
            "status": "success",
            "message": f"Ordered {item_name}",
            "id": new_order.id_order,
            "assigned_waiter": assigned_waiter.full_name if assigned_waiter else "Unassigned"
        })
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@api_view(['POST'])
def cancel_session(request):
    """Allows a user to leave the queue or stop playing."""
    session_id = request.data.get('session_id')
    client_id = request.data.get('client_id')
    
    try:
        session = DailyGameSession.objects.get(session_id=session_id)
        # Security check: only the owner can cancel
        if str(session.client.id) != str(client_id):
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            
        if session.status == 'playing':
            session.status = 'completed'
        else:
            session.status = 'cancelled'
        
        # Keep game_status as active to maintain traceability in the line
        session.game_status = 'active'
        session.save()
        return Response({"status": "success", "message": "Left the queue"})
    except DailyGameSession.DoesNotExist:
        return Response({"detail": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def confirm_play(request):
    """User confirms they are ready to play after being notified."""
    session_id = request.data.get('session_id')
    client_id = request.data.get('client_id')
    
    try:
        session = DailyGameSession.objects.get(session_id=session_id)
        if str(session.client.id) != str(client_id):
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            
        if session.status != 'notified':
            return Response({"detail": "It is not your turn yet or turn expired"}, status=status.HTTP_400_BAD_REQUEST)
            
        session.status = 'playing'
        session.notified_at = timezone.now() # Reset timestamp to track game duration
        session.save()
        return Response({"status": "success", "message": "Enjoy your game!"})
    except DailyGameSession.DoesNotExist:
        return Response({"detail": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_user_game_history(request):
    """Returns past played games history for a specific user."""
    client_id = request.query_params.get('client_id')
    
    if not client_id:
        return Response({"detail": "client_id required"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        user = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
    # Get all game sessions for this client
    sessions = DailyGameSession.objects.filter(client=user).order_by('-created_at')
    
    return Response([{
        "session_id": s.session_id,
        "table_name": s.game_table.gamet_name if s.game_table else "TBD",
        "game_type": s.game_table.game_type.name if s.game_table and s.game_table.game_type else "TBD",
        "game_type_image": s.game_table.game_type.image_path if s.game_table and s.game_table.game_type else "",
        "status": s.status,
        "daily_number": s.daily_number,
        "created_at": s.created_at,
        "notified_at": s.notified_at,
        "opponent": s.opponent.full_name_cl if s.opponent else None,
    } for s in sessions])



@api_view(['GET'])
@permission_classes([AllowAny])
def get_connected_players(request):
    client_id = request.query_params.get('client_id')
    now = timezone.now()
    fifteen_seconds_ago = now - timezone.timedelta(seconds=15)
    
    # Players active in the last 15 seconds (excluding the requesting client)
    active_query = Client.objects.filter(last_seen_at__gte=fifteen_seconds_ago)
    if client_id:
        active_query = active_query.exclude(id=client_id)
        
    connected_players = list(active_query)
    
    # Categorize
    idle = []
    finishing = []
    
    today = now.date()
    
    for player in connected_players:
        # Check if player is playing
        active_session = DailyGameSession.objects.filter(
            client=player,
            status__in=['playing', 'notified'],
            game_status='active',
            created_at__date=today
        ).first()
        
        if not active_session:
            # Also check as opponent
            active_session = DailyGameSession.objects.filter(
                opponent=player,
                status__in=['playing', 'notified'],
                game_status='active',
                created_at__date=today
            ).first()
            
        if not active_session:
            idle.append({
                "id": player.id,
                "full_name": player.full_name_cl or f"Player #{player.id}",
            })
        else:
            # check if they've been playing for >15 minutes
            is_finishing = False
            if active_session.status == 'playing' and active_session.notified_at:
                elapsed = (now - active_session.notified_at).total_seconds()
                if elapsed > 900: # 15 minutes
                    is_finishing = True
                    
            if is_finishing:
                finishing.append({
                    "id": player.id,
                    "full_name": player.full_name_cl or f"Player #{player.id}",
                })
                
    return Response({
        "idle": idle,
        "finishing": finishing
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def send_play_request(request):
    sender_id = request.data.get('sender_id')
    receiver_id = request.data.get('receiver_id')
    table_id = request.data.get('table_id')
    
    if not sender_id or not receiver_id or not table_id:
        return Response({"detail": "sender_id, receiver_id, and table_id are required"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        sender = Client.objects.get(id=sender_id)
        receiver = Client.objects.get(id=receiver_id)
        table = GamingTable.objects.get(id_gamet=table_id)
        
        # Check if there's already an active play request between them
        existing = PlayRequest.objects.filter(
            sender=sender,
            receiver=receiver,
            status='pending'
        ).first()
        
        if existing:
            # Auto-expire if older than 10 seconds
            elapsed = (timezone.now() - existing.created_at).total_seconds()
            if elapsed <= 10:
                return Response({"detail": "A request is already pending to this player"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                existing.status = 'expired'
                existing.save()
                
        req = PlayRequest.objects.create(
            sender=sender,
            receiver=receiver,
            game_table=table,
            status='pending'
        )
        
        return Response({"status": "success", "request_id": req.id})
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([AllowAny])
def poll_play_requests(request):
    client_id = request.query_params.get('client_id')
    if not client_id:
        return Response({"detail": "client_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
    now = timezone.now()
    
    # Expiry logic for pending requests
    pending_requests = PlayRequest.objects.filter(receiver_id=client_id, status='pending')
    
    active_reqs = []
    for req in pending_requests:
        elapsed = (now - req.created_at).total_seconds()
        if elapsed > 10:
            req.status = 'expired'
            req.save()
        else:
            active_reqs.append({
                "id": req.id,
                "sender_name": req.sender.full_name_cl or f"Player #{req.sender.id}",
                "table_name": req.game_table.gamet_name,
                "table_id": req.game_table.id_gamet,
                "time_left": max(0, int(10 - elapsed))
            })
            
    return Response(active_reqs)

@api_view(['POST'])
@permission_classes([AllowAny])
def respond_play_request(request):
    request_id = request.data.get('request_id')
    response_val = request.data.get('response') # 'accepted' or 'refused'
    
    if not request_id or not response_val:
        return Response({"detail": "request_id and response are required"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        req = PlayRequest.objects.get(id=request_id)
        
        # Check expiry (10 seconds)
        elapsed = (timezone.now() - req.created_at).total_seconds()
        if elapsed > 10:
            req.status = 'expired'
            req.save()
            return Response({"detail": "Request has expired"}, status=status.HTTP_400_BAD_REQUEST)
            
        if req.status != 'pending':
            return Response({"detail": "Request already handled"}, status=status.HTTP_400_BAD_REQUEST)
            
        req.status = response_val
        req.save()
        
        if response_val == 'accepted':
            today = timezone.now().date()
            # 1. Cancel any active queues/playing sessions for both players to avoid overlaps
            DailyGameSession.objects.filter(
                client_id__in=[req.sender.id, req.receiver.id],
                status__in=['waiting', 'notified', 'playing'],
                created_at__date=today
            ).update(status='completed')
            
            DailyGameSession.objects.filter(
                opponent_id__in=[req.sender.id, req.receiver.id],
                status__in=['waiting', 'notified', 'playing'],
                created_at__date=today
            ).update(status='completed')
            
            # 2. Create the multiplayer Game Session
            session = DailyGameSession.objects.create(
                client=req.sender,
                opponent=req.receiver,
                game_table=req.game_table,
                status='playing',
                daily_number=99,  # special number for match duels
                notified_at=timezone.now()
            )
            return Response({"status": "success", "session_id": session.session_id})
            
        return Response({"status": "success", "message": "Request declined"})
    except PlayRequest.DoesNotExist:
        return Response({"detail": "Request not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def set_session_winner(request):
    session_id = request.data.get('session_id')
    winner_id = request.data.get('winner_id') # Can be client_id, opponent_id or None for draw
    
    if not session_id:
        return Response({"detail": "session_id required"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        session = DailyGameSession.objects.get(session_id=session_id)
        if winner_id:
            winner = Client.objects.get(id=winner_id)
            session.winner = winner
        else:
            session.winner = None
        session.save()
        return Response({"status": "success"})
    except DailyGameSession.DoesNotExist:
        return Response({"detail": "Session not found"}, status=status.HTTP_404_NOT_FOUND)
    except Client.DoesNotExist:
        return Response({"detail": "Winner player not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def get_user_orders(request):
    """Returns orders for a specific user."""
    client_id = request.query_params.get('client_id')
    if not client_id:
        return Response({"detail": "client_id required"}, status=status.HTTP_400_BAD_REQUEST)
    
    orders = Order.objects.filter(client_id=client_id).order_by('-created_at')
    return Response([{
        "id": o.id_order,
        "name": o.name_order,
        "price": o.price,
        "status": o.status,
        "created_at": o.created_at,
        "game_table_name": o.game_table.gamet_name if o.game_table else None,
        "order_table_number": o.cafe_table_number, # Distinguish: Order Table (1-25)
        "waiter": o.waiter.full_name if o.waiter else "Unassigned"
    } for o in orders])

@api_view(['GET'])
def get_profile(request):
    """Returns profile information for a specific user."""
    client_id = request.query_params.get('client_id')
    if not client_id:
        return Response({"detail": "client_id required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = Client.objects.get(id=client_id)
        # Split full name
        names = user.full_name_cl.split(' ', 1) if user.full_name_cl else ["", ""]
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else ""
        
        return Response({
            "first_name": first_name,
            "last_name": last_name,
            "phone": user.phone_cl,
            "email": user.email_cl,
            "photo_path": user.image_path
        })
    except Client.DoesNotExist:
        return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def update_profile(request):
    """Updates user profile information."""
    data = request.data
    client_id = data.get('client_id')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    phone = data.get('phone')
    email = data.get('email')
    password = data.get('password')
    photo = request.FILES.get('photo')
    
    if not client_id:
        return Response({"detail": "client_id required"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        user = Client.objects.get(id=client_id)
        
        if first_name and last_name:
            user.full_name_cl = f"{first_name} {last_name}"
            
        if phone:
            # Check if phone is taken by another user
            existing = Client.objects.filter(phone_cl=phone).exclude(id=user.id).first()
            if existing:
                return Response({"detail": "Phone number already in use"}, status=status.HTTP_400_BAD_REQUEST)
            user.phone_cl = phone
            
        if email:
            # Check if email is taken by another user
            existing = Client.objects.filter(email_cl=email).exclude(id=user.id).first()
            if existing:
                return Response({"detail": "Email already in use"}, status=status.HTTP_400_BAD_REQUEST)
            user.email_cl = email
            
        if password:
            import hashlib
            pw_to_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            user.password_hash = pwd_context.hash(pw_to_hash)
            
        if photo:
            upload_dir = os.path.join(settings.BASE_DIR, "uploads/user_photos")
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, photo.name)
            
            with open(file_path, "wb") as buffer:
                for chunk in photo.chunks():
                    buffer.write(chunk)
            
            # Save relative path for serving
            user.image_path = f"/uploads/user_photos/{photo.name}"
            
        user.save()
        return Response({
            "status": "success", 
            "message": "Profile updated",
            "user_name": user.full_name_cl
        })
    except Client.DoesNotExist:
        return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def cancel_order(request):
    """Allows a user to cancel a pending order."""
    order_id = request.data.get('order_id')
    client_id = request.data.get('client_id')
    
    try:
        order = Order.objects.get(id_order=order_id)
        if str(order.client.id) != str(client_id):
            return Response({"detail": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
            
        if order.status != 'pending':
            return Response({"detail": "Order cannot be cancelled in current status"}, status=status.HTTP_400_BAD_REQUEST)
            
        order.status = 'cancelled'
        order.save()
        return Response({"status": "success", "message": "Order cancelled"})
    except Order.DoesNotExist:
        return Response({"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def get_cafe_tables(request):
    """Returns status of cafe tables 1-25."""
    now = timezone.now()
    # Auto-release tables not confirmed in 1 hour
    timeout = now - timedelta(hours=1)
    CafeTableOccupation.objects.filter(status='occupied', last_confirmed_at__lt=timeout).update(status='free')
    
    occupations = CafeTableOccupation.objects.filter(status='occupied')
    occupied_map = {o.table_number: o for o in occupations}
    
    tables = []
    for i in range(1, 26):
        occ = occupied_map.get(i)
        last_confirmed = occ.last_confirmed_at if occ else None
        if last_confirmed and timezone.is_naive(last_confirmed):
            last_confirmed = timezone.make_aware(last_confirmed)
            
        tables.append({
            "number": i,
            "status": "occupied" if occ else "free",
            "client_id": occ.client_id if occ else None,
            "last_confirmed": last_confirmed,
            "timer": int((now - last_confirmed).total_seconds()) if last_confirmed else 0
        })
    return Response(tables)

@api_view(['POST'])
def occupy_cafe_table(request):
    """User sits at a cafe table."""
    client_id = request.data.get('client_id')
    table_number = request.data.get('table_number')
    
    if not client_id or not table_number:
        return Response({"detail": "Missing data"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        # Check if already taken
        if CafeTableOccupation.objects.filter(table_number=table_number, status='occupied').exists():
            return Response({"detail": "Table already taken"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Clear user's previous occupations if any
        CafeTableOccupation.objects.filter(client_id=client_id).update(status='free')
        
        # Occupy or update
        occ, created = CafeTableOccupation.objects.update_or_create(
            table_number=table_number,
            defaults={'client_id': client_id, 'status': 'occupied', 'last_confirmed_at': timezone.now()}
        )
        return Response({"status": "success", "message": f"Table {table_number} occupied"})
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def confirm_cafe_table(request):
    """User confirms they are still at the table."""
    client_id = request.data.get('client_id')
    table_number = request.data.get('table_number')
    
    try:
        occ = CafeTableOccupation.objects.get(table_number=table_number, client_id=client_id, status='occupied')
        occ.last_confirmed_at = timezone.now()
        occ.save()
        return Response({"status": "success", "message": "Stay confirmed"})
    except CafeTableOccupation.DoesNotExist:
        return Response({"detail": "Occupation not found"}, status=status.HTTP_404_NOT_FOUND)
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """Admin login with credentials from DB."""
    try:
        username = request.data.get('username')
        password = request.data.get('password')
        login_type = request.data.get('login_type', 'admin')  # 'admin' or 'screen'
        
        if username:
            username = username.strip()
        
        if not username or not password:
            return Response({"detail": "Username and password required"}, status=status.HTTP_400_BAD_REQUEST)
        
        admin = Admin.objects.filter(username__iexact=username).first()
        if admin:
            # We expect double hashing on frontend for user login, but admin might be simpler or same
            # Let's stay consistent: frontend sends plain password, we hash sha256 then verify with pbkdf2
            pw_to_check = hashlib.sha256(password.encode('utf-8')).hexdigest()
            is_valid = False
            
            if admin.password_hash:
                try:
                    is_valid = pwd_context.verify(pw_to_check, admin.password_hash)
                except Exception:
                    pass
                
                # Fallback for plain text or pure SHA-256 legacy hashes
                if not is_valid and (admin.password_hash == pw_to_check or admin.password_hash == password):
                    is_valid = True

            if is_valid:
                config = SessionConfig.get_config()
                session_hours = config.screen_session_hours if login_type == 'screen' else config.admin_session_hours
                return Response({
                    "status": "success",
                    "token": f"token-{admin.id}-{admin.admin_level}",
                    "user": admin.username,
                    "admin_level": admin.admin_level,
                    "session_duration_hours": session_hours,
                    "login_timestamp": timezone.now().isoformat()
                })
                
        return Response({"detail": "Access Denied: Invalid Credentials"}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        import traceback
        print(f"admin_login error: {traceback.format_exc()}")
        return Response({"detail": f"Login error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
def manage_menu(request):
    if request.method == 'GET':
        items = Menu.objects.all().order_by('category', 'name')
        return Response([{
            "id": i.id,
            "name": i.name,
            "description": i.description,
            "price": i.price,
            "category": i.category,
            "image_path": i.image_path,
            "is_available": i.is_available,
            "popularity": i.popularity
        } for i in items])
        
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    data = request.data
    item = Menu.objects.create(
        name=data.get('name'),
        description=data.get('description'),
        price=data.get('price'),
        category=data.get('category'),
        image_path=data.get('image_path'),
        is_available=data.get('is_available', True),
        popularity=data.get('popularity', 0)
    )
    return Response({"status": "success", "id": item.id})

@api_view(['PUT', 'DELETE'])
def menu_detail(request, pk):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        item = Menu.objects.get(pk=pk)
    except Menu.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'PUT':
        data = request.data
        item.name = data.get('name', item.name)
        item.description = data.get('description', item.description)
        item.price = data.get('price', item.price)
        item.category = data.get('category', item.category)
        item.image_path = data.get('image_path', item.image_path)
        item.is_available = data.get('is_available', item.is_available)
        item.popularity = data.get('popularity', item.popularity)
        item.save()
        return Response({"status": "updated"})
    
    if request.method == 'DELETE':
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
def manage_waiters(request):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        waiters = Waiter.objects.all().order_by('full_name')
        return Response([{
            "id": w.id,
            "full_name": w.full_name,
            "phone": w.phone,
            "email": w.email,
            "status": w.status,
            "role": w.role,
            "current_load": w.current_load,
            "joined_at": w.joined_at
        } for w in waiters])
    
    data = request.data
    waiter = Waiter.objects.create(
        full_name=data.get('full_name'),
        phone=data.get('phone'),
        email=data.get('email'),
        pin=data.get('pin'),
        role=data.get('role', 'waiter'),
        status=data.get('status', 'active')
    )
    return Response({"status": "success", "id": waiter.id})

@api_view(['PUT', 'DELETE'])
def waiter_detail(request, pk):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        waiter = Waiter.objects.get(pk=pk)
    except Waiter.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'PUT':
        data = request.data
        waiter.full_name = data.get('full_name', waiter.full_name)
        waiter.phone = data.get('phone', waiter.phone)
        waiter.email = data.get('email', waiter.email)
        waiter.role = data.get('role', waiter.role)
        waiter.status = data.get('status', waiter.status)
        waiter.save()
        return Response({"status": "updated"})
    
    if request.method == 'DELETE':
        waiter.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET'])
def get_all_orders(request):
    """Admin view to see today's orders by default."""
    if not check_admin_role(request, "simple_admin"):
        return Response({"detail": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    today = timezone.now().date()
    orders = Order.objects.filter(created_at__date=today).order_by('-created_at')
    return Response([{
        "id": o.id_order,
        "name": o.name_order,
        "price": str(o.price),
        "status": o.status,
        "waiter": o.waiter.full_name if o.waiter else "None",
        "customer": o.client.full_name_cl if o.client else "Guest",
        "created_at": o.created_at,
        "table": o.cafe_table_number if o.cafe_table_number else (o.game_table.gamet_name if o.game_table else "General")
    } for o in orders])

@api_view(['PUT', 'DELETE'])
def order_detail(request, pk):
    if not check_admin_role(request, "simple_admin"):
        return Response({"detail": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'PUT':
        data = request.data
        order.name_order = data.get('name', order.name_order)
        order.price = data.get('price', order.price)
        order.status = data.get('status', order.status)
        order.save()
        return Response({"status": "updated"})
    
    if request.method == 'DELETE':
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
@api_view(['PUT'])
def update_order_status(request, pk):
    if not check_admin_role(request, "simple_admin"):
        return Response({"detail": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    """Update the status of a specific order."""
    try:
        order = Order.objects.get(pk=pk)
        new_status = request.data.get('status')
        if new_status in ['pending', 'preparing', 'served', 'cancelled']:
            old_status = order.status
            order.status = new_status
            order.save()
            
            # If transitioning to served, create financial record and reduce waiter load
            if new_status == 'served' and old_status != 'served':
                FinancialRecord.objects.get_or_create(
                    order=order,
                    defaults={
                        'amount': order.price,
                        'record_type': 'revenue',
                        'payment_method': 'cash', # Default to cash
                        'status': 'cleared'
                    }
                )
                if order.waiter:
                    order.waiter.current_load = max(0, order.waiter.current_load - 1)
                    order.waiter.save()
            return Response({"status": "success", "message": f"Order marked as {new_status}"})
        return Response({"detail": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
    except Order.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

@api_view(['GET', 'POST'])
def manage_clients(request):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        clients = Client.objects.all().order_by('full_name_cl')
        return Response([{
            "id": c.id,
            "full_name": c.full_name_cl,
            "phone": c.phone_cl,
            "email": c.email_cl
        } for c in clients])
    
    data = request.data
    password = data.get('password')
    password_hash = None
    if password:
        import hashlib
        pw_to_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        password_hash = pwd_context.hash(pw_to_hash)

    client = Client.objects.create(
        full_name_cl=data.get('full_name'),
        phone_cl=data.get('phone'),
        email_cl=data.get('email'),
        password_hash=password_hash
    )
    return Response({"status": "success", "id": client.id})

@api_view(['PUT', 'DELETE'])
def client_detail(request, pk):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        client = Client.objects.get(pk=pk)
    except Client.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'PUT':
        data = request.data
        client.full_name_cl = data.get('full_name', client.full_name_cl)
        client.phone_cl = data.get('phone', client.phone_cl)
        client.email_cl = data.get('email', client.email_cl)
        
        password = data.get('password')
        if password:
            import hashlib
            pw_to_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            client.password_hash = pwd_context.hash(pw_to_hash)
            
        client.save()
        return Response({"status": "updated"})
    
    if request.method == 'DELETE':
        client.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
def manage_sessions(request):
    if not check_admin_role(request, "simple_admin"):
        return Response({"detail": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        today = timezone.now().date()
        sessions = DailyGameSession.objects.filter(created_at__date=today).order_by('-created_at')
        return Response([{
            "id": s.session_id,
            "client": s.client.full_name_cl if s.client else "Unknown",
            "client_id": s.client.id if s.client else None,
            "opponent": s.opponent.full_name_cl if s.opponent else None,
            "opponent_id": s.opponent.id if s.opponent else None,
            "table": s.game_table.gamet_name if s.game_table else "TBD",
            "status": s.status,
            "daily_number": s.daily_number,
            "created_at": s.created_at,
            "winner": s.winner.full_name_cl if s.winner else None
        } for s in sessions])
    
    if request.method == 'POST':
        data = request.data
        session = DailyGameSession.objects.create(
            client_id=data.get('client_id'),
            game_table_id=data.get('table_id'),
            status=data.get('status', 'waiting'),
            daily_number=data.get('daily_number', 0)
        )
        return Response({"status": "success", "id": session.session_id})

@api_view(['PUT', 'DELETE'])
def session_detail(request, pk):
    if not check_admin_role(request, "simple_admin"):
        return Response({"detail": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        session = DailyGameSession.objects.get(pk=pk)
    except DailyGameSession.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'PUT':
        data = request.data
        session.status = data.get('status', session.status)
        session.daily_number = data.get('daily_number', session.daily_number)
        session.save()
        return Response({"status": "updated"})
    
    if request.method == 'DELETE':
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
@api_view(['GET', 'POST'])
def manage_financials(request):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        today = timezone.now().date()
        records = FinancialRecord.objects.filter(recorded_at__date=today).order_by('-recorded_at')
        return Response([{
            "id": r.id,
            "order": r.order.name_order if r.order else "Manual Entry",
            "amount": str(r.amount),
            "type": r.record_type,
            "method": r.payment_method,
            "status": r.status,
            "note": r.comptable_note,
            "date": r.recorded_at
        } for r in records])
    
    data = request.data
    record = FinancialRecord.objects.create(
        amount=data.get('amount'),
        record_type=data.get('record_type', 'revenue'),
        payment_method=data.get('payment_method', 'cash'),
        status=data.get('status', 'cleared'),
        comptable_note=data.get('note')
    )
    return Response({"status": "success", "id": record.id})

@api_view(['PUT', 'DELETE'])
def financial_detail(request, pk):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        record = FinancialRecord.objects.get(pk=pk)
    except FinancialRecord.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'PUT':
        data = request.data
        record.amount = data.get('amount', record.amount)
        record.record_type = data.get('record_type', record.record_type)
        record.payment_method = data.get('payment_method', record.payment_method)
        record.status = data.get('status', record.status)
        record.comptable_note = data.get('note', record.comptable_note)
        record.save()
        return Response({"status": "updated"})
    
    if request.method == 'DELETE':
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET'])
def get_master_history(request):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    """Comprehensive historical data aggregator with filtering."""
    
    # 1. Sessions History
    sessions = DailyGameSession.objects.all().order_by('-created_at')
    session_data = [{
        "category": "Session",
        "detail": f"{s.client.full_name_cl if s.client else 'Unknown'} at {s.game_table.gamet_name if s.game_table else 'TBD'}",
        "status": s.status,
        "date": s.created_at,
        "info": f"Queue #{s.daily_number}"
    } for s in sessions]
    
    # 2. Orders History
    orders = Order.objects.all().order_by('-created_at')
    order_data = [{
        "category": "Order",
        "detail": f"{o.name_order} for {o.client.full_name_cl if o.client else 'Guest'}",
        "status": o.status,
        "date": o.created_at,
        "info": f"{o.price} DH (By {o.waiter.full_name if o.waiter else 'System'})"
    } for o in orders]
    
    # 3. Financial History
    financials = FinancialRecord.objects.all().order_by('-recorded_at')
    financial_data = [{
        "category": "Finance",
        "detail": f"{r.record_type.upper()}: {r.order.name_order if r.order else 'Manual Entry'}",
        "status": r.status,
        "date": r.recorded_at,
        "info": f"{r.amount} DH ({r.payment_method})"
    } for r in financials]
    
    combined = sorted(session_data + order_data + financial_data, key=lambda x: x['date'], reverse=True)
    
    # Apply Basic Filtering if requested
    search = request.query_params.get('search', '').lower()
    type_filter = request.query_params.get('type')
    
    if search:
        combined = [x for x in combined if search in x['detail'].lower() or search in x['info'].lower()]
    if type_filter:
        combined = [x for x in combined if x['category'] == type_filter]
        
    return Response(combined)

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def manage_game_types(request):
    if request.method == 'GET':
        gtypes = GameType.objects.all().order_by('name')
        return Response([{
            "id": g.id,
            "name": g.name,
            "image_path": g.image_path,
            "station_count": g.station_count,
            "description": g.description
        } for g in gtypes])
        
    if request.method == 'POST':
        if not check_admin_role(request, "super_admin"):
            return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        data = request.data
        gtype = GameType.objects.create(
            name=data.get('name'),
            image_path=data.get('image_path'),
            station_count=int(data.get('station_count', 1)),
            description=data.get('description')
        )
        # Automatically create/verify GamingTable entries
        for i in range(1, gtype.station_count + 1):
            GamingTable.objects.get_or_create(
                game_type=gtype,
                gamet_number=i,
                defaults={'gamet_name': f"{gtype.name} Station {i}"}
            )
        return Response({"status": "success", "id": gtype.id})

@api_view(['GET', 'PUT', 'DELETE'])
def game_type_detail(request, pk):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        gtype = GameType.objects.get(pk=pk)
    except GameType.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response({
            "id": gtype.id,
            "name": gtype.name,
            "image_path": gtype.image_path,
            "station_count": gtype.station_count,
            "description": gtype.description
        })

    if request.method == 'PUT':
        data = request.data
        gtype.name = data.get('name', gtype.name)
        gtype.image_path = data.get('image_path', gtype.image_path)
        gtype.station_count = int(data.get('station_count', gtype.station_count))
        gtype.description = data.get('description', gtype.description)
        gtype.save()
        
        # Verify stations
        for i in range(1, gtype.station_count + 1):
            GamingTable.objects.get_or_create(
                game_type=gtype,
                gamet_number=i,
                defaults={'gamet_name': f"{gtype.name} Station {i}"}
            )
        # Cleanup extra stations if count was reduced
        GamingTable.objects.filter(game_type=gtype, gamet_number__gt=gtype.station_count).delete()
        return Response({"status": "updated"})
    
    if request.method == 'DELETE':
        gtype.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
def manage_gaming_tables(request):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        
    if request.method == 'GET':
        tables = GamingTable.objects.select_related('game_type').all().order_by('id_gamet')
        return Response([{
            "id": t.id_gamet,
            "name": t.gamet_name,
            "number": t.gamet_number,
            "club": t.gamet_club,
            "game_type_id": t.game_type.id if t.game_type else None,
            "game_type_name": t.game_type.name if t.game_type else None
        } for t in tables])
        
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        
    data = request.data
    gtype_id = data.get('game_type_id')
    gtype = None
    if gtype_id:
        try:
            gtype = GameType.objects.get(pk=gtype_id)
        except GameType.DoesNotExist:
            return Response({"detail": "Game Type not found"}, status=status.HTTP_400_BAD_REQUEST)
            
    table = GamingTable.objects.create(
        gamet_name=data.get('name'),
        gamet_number=int(data.get('number', 1)),
        gamet_club=data.get('club', 'CueClub'),
        game_type=gtype
    )
    return Response({"status": "success", "id": table.id_gamet})

@api_view(['GET', 'PUT', 'DELETE'])
def gaming_table_detail(request, pk):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        
    try:
        table = GamingTable.objects.get(pk=pk)
    except GamingTable.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'GET':
        return Response({
            "id": table.id_gamet,
            "name": table.gamet_name,
            "number": table.gamet_number,
            "club": table.gamet_club,
            "game_type_id": table.game_type.id if table.game_type else None,
            "game_type_name": table.game_type.name if table.game_type else None
        })
        
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
        
    if request.method == 'PUT':
        data = request.data
        table.gamet_name = data.get('name', table.gamet_name)
        table.gamet_number = int(data.get('number', table.gamet_number))
        table.gamet_club = data.get('club', table.gamet_club)
        
        gtype_id = data.get('game_type_id')
        if gtype_id is not None:
            if gtype_id == "":
                table.game_type = None
            else:
                try:
                    table.game_type = GameType.objects.get(pk=gtype_id)
                except GameType.DoesNotExist:
                    return Response({"detail": "Game Type not found"}, status=status.HTTP_400_BAD_REQUEST)
        table.save()
        return Response({"status": "updated"})
        
    if request.method == 'DELETE':
        table.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'POST'])
def manage_admins(request):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        admins = Admin.objects.all().order_by('-created_at')
        return Response([{
            "id": a.id,
            "username": a.username,
            "admin_level": a.admin_level,
            "created_at": a.created_at
        } for a in admins])
    
    if request.method == 'POST':
        data = request.data
        username = data.get('username')
        password = data.get('password')
        level = data.get('admin_level', 'simple_admin')

        if not username or not password:
            return Response({"detail": "Username and password required"}, status=status.HTTP_400_BAD_REQUEST)

        if Admin.objects.filter(username=username).exists():
            return Response({"detail": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

        hashed = pwd_context.hash(hashlib.sha256(password.encode('utf-8')).hexdigest())
        admin = Admin.objects.create(
            username=username,
            password_hash=hashed,
            admin_level=level
        )
        return Response({"status": "success", "id": admin.id})

@api_view(['PUT', 'DELETE'])
def admin_detail(request, pk):
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        admin = Admin.objects.get(pk=pk)
    except Admin.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'PUT':
        data = request.data
        admin.username = data.get('username', admin.username)
        admin.admin_level = data.get('admin_level', admin.admin_level)
        
        password = data.get('password')
        if password:
            hashed = pwd_context.hash(hashlib.sha256(password.encode('utf-8')).hexdigest())
            admin.password_hash = hashed
            
        admin.save()
        return Response({"status": "updated"})
    
    if request.method == 'DELETE':
        if admin.username == "admin":
             return Response({"detail": "Cannot delete master admin"}, status=status.HTTP_400_BAD_REQUEST)
        admin.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET', 'PUT'])
def manage_session_config(request):
    """View or update session duration settings. Super admin only."""
    if not check_admin_role(request, "super_admin"):
        return Response({"detail": "Super Admin access required"}, status=status.HTTP_403_FORBIDDEN)
    
    config = SessionConfig.get_config()
    
    if request.method == 'GET':
        return Response({
            "admin_session_hours": config.admin_session_hours,
            "screen_session_hours": config.screen_session_hours,
            "user_session_hours": config.user_session_hours,
            "updated_at": config.updated_at
        })
    
    if request.method == 'PUT':
        data = request.data
        admin_hours = data.get('admin_session_hours')
        screen_hours = data.get('screen_session_hours')
        user_hours = data.get('user_session_hours')
        
        if admin_hours is not None:
            admin_hours = float(admin_hours)
            if admin_hours < 0.5 or admin_hours > 168:  # Min 30min, Max 1 week
                return Response({"detail": "Admin session must be between 0.5 and 168 hours"}, status=status.HTTP_400_BAD_REQUEST)
            config.admin_session_hours = admin_hours
        
        if screen_hours is not None:
            screen_hours = float(screen_hours)
            if screen_hours < 1 or screen_hours > 168:
                return Response({"detail": "Screen session must be between 1 and 168 hours"}, status=status.HTTP_400_BAD_REQUEST)
            config.screen_session_hours = screen_hours
        
        if user_hours is not None:
            user_hours = float(user_hours)
            if user_hours < 0.5 or user_hours > 168:
                return Response({"detail": "User session must be between 0.5 and 168 hours"}, status=status.HTTP_400_BAD_REQUEST)
            config.user_session_hours = user_hours
        
        config.save()
        return Response({
            "status": "success",
            "admin_session_hours": config.admin_session_hours,
            "screen_session_hours": config.screen_session_hours,
            "user_session_hours": config.user_session_hours
        })

@api_view(['POST'])
@permission_classes([AllowAny])
def validate_session(request):
    """Validates if a session is still active based on login timestamp and configured duration."""
    login_timestamp = request.data.get('login_timestamp')
    session_type = request.data.get('session_type', 'admin')  # 'admin' or 'screen'
    
    if not login_timestamp:
        return Response({"valid": False, "reason": "No login timestamp provided"})
    
    try:
        from datetime import datetime
        login_time = datetime.fromisoformat(login_timestamp)
        if timezone.is_naive(login_time):
            login_time = timezone.make_aware(login_time)
        
        config = SessionConfig.get_config()
        if session_type == 'screen':
            max_hours = config.screen_session_hours
        elif session_type == 'user':
            max_hours = config.user_session_hours
        else:
            max_hours = config.admin_session_hours
        elapsed = (timezone.now() - login_time).total_seconds() / 3600
        
        if elapsed > max_hours:
            return Response({
                "valid": False,
                "reason": "Session expired",
                "elapsed_hours": round(elapsed, 2),
                "max_hours": max_hours
            })
        
        return Response({
            "valid": True,
            "remaining_hours": round(max_hours - elapsed, 2),
            "max_hours": max_hours
        })
    except Exception as e:
        return Response({"valid": False, "reason": str(e)})


