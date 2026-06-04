from django.db import models

class Client(models.Model):
    id = models.AutoField(primary_key=True, db_column='id_client')
    full_name_cl = models.CharField(max_length=255, db_column='full_name_cl', blank=True, null=True)
    phone_cl = models.CharField(max_length=255, db_column='phone_cl', unique=True, blank=True, null=True)
    email_cl = models.CharField(max_length=255, db_column='email_cl', unique=True, blank=True, null=True)
    password_hash = models.TextField(db_column='password_hash', blank=True, null=True)
    image_path = models.TextField(db_column='image_path', blank=True, null=True)
    last_seen_at = models.DateTimeField(db_column='last_seen_at', blank=True, null=True)

    class Meta:
        db_table = 'client'
        managed = True

    def __str__(self):
        return self.full_name_cl or f"Client {self.id}"

class GameType(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    image_path = models.TextField(blank=True, null=True)
    station_count = models.IntegerField(default=1) # Total stations for this game type
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'game_type'

    def __str__(self):
        return self.name

class GamingTable(models.Model):
    id_gamet = models.AutoField(primary_key=True)
    gamet_name = models.CharField(max_length=255, blank=True, null=True)
    gamet_number = models.IntegerField(blank=True, null=True) # Station number (1, 2, ...)
    gamet_club = models.CharField(max_length=255, blank=True, null=True)
    game_type = models.ForeignKey(GameType, on_delete=models.SET_NULL, null=True, blank=True, related_name='tables')

    class Meta:
        db_table = 'gaming_table'
        managed = True

    def __str__(self):
        return self.gamet_name or f"Table {self.id_gamet}"

class DailyGameSession(models.Model):
    session_id = models.AutoField(primary_key=True)
    client = models.ForeignKey(Client, models.DO_NOTHING, blank=True, null=True)
    game_table = models.ForeignKey(GamingTable, models.DO_NOTHING, blank=True, null=True)
    daily_number = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=50, default='waiting') # waiting, notified, playing, cancelled, completed
    game_status = models.CharField(max_length=50, default='active') # active, canceled
    notified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    opponent = models.ForeignKey(Client, models.SET_NULL, blank=True, null=True, related_name='opponent_sessions')
    winner = models.ForeignKey(Client, models.SET_NULL, blank=True, null=True, related_name='won_sessions')

    class Meta:
        db_table = 'daily_game_session'
        managed = True

class PlayRequest(models.Model):
    id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(Client, models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(Client, models.CASCADE, related_name='received_requests')
    game_table = models.ForeignKey(GamingTable, models.CASCADE)
    status = models.CharField(max_length=50, default='pending') # pending, accepted, refused, expired
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'play_request'

class Order(models.Model):
    id_order = models.AutoField(primary_key=True)
    name_order = models.CharField(max_length=255, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    client = models.ForeignKey(Client, models.DO_NOTHING, blank=True, null=True)
    game_table = models.ForeignKey(GamingTable, models.DO_NOTHING, blank=True, null=True)
    cafe_table_number = models.IntegerField(blank=True, null=True)
    waiter = models.ForeignKey('Waiter', models.SET_NULL, blank=True, null=True, related_name='orders')
    status = models.CharField(max_length=50, default='pending') # pending, preparing, served, cancelled
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)

    class Meta:
        db_table = 'orders'
        managed = True

class CafeTableOccupation(models.Model):
    client = models.ForeignKey(Client, models.DO_NOTHING, blank=True, null=True)
    table_number = models.IntegerField(unique=True)
    last_confirmed_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50, default='occupied') # occupied, free

    class Meta:
        db_table = 'cafe_table_occupation'
        managed = True

class Menu(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100) # Coffee, Tea, Cold, Snacks
    image_path = models.TextField(blank=True, null=True)
    is_available = models.BooleanField(default=True)
    popularity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'menu'
        managed = True

class Waiter(models.Model):
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    pin = models.CharField(max_length=10, blank=True, null=True) # For simple login
    role = models.CharField(max_length=50, default='waiter') # waiter, manager, comptable
    status = models.CharField(max_length=50, default='active') # active, on_break, off_duty
    current_load = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'waiter'

class FinancialRecord(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.OneToOneField(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='financial_audit')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    record_type = models.CharField(max_length=50, default='revenue') # revenue, expense, payout
    payment_method = models.CharField(max_length=50, default='cash') # cash, card, vault
    status = models.CharField(max_length=50, default='cleared') # pending, cleared, disputed
    comptable_note = models.TextField(blank=True, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'financial_record'

class Admin(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=255, unique=True)
    password_hash = models.TextField()
    admin_level = models.CharField(max_length=50, default='simple_admin') # super_admin, simple_admin
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_user'

class SessionConfig(models.Model):
    """Singleton configuration for session durations (in hours)."""
    id = models.AutoField(primary_key=True)
    admin_session_hours = models.FloatField(default=6.0)  # Admin panel session duration
    screen_session_hours = models.FloatField(default=12.0)  # Screen display session duration
    user_session_hours = models.FloatField(default=24.0)  # User/member session duration
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'session_config'
        managed = True

    @classmethod
    def get_config(cls):
        """Returns the singleton config, creating it with defaults if needed."""
        config, _ = cls.objects.get_or_create(pk=1)
        return config

    def __str__(self):
        return f"Session Config: Admin={self.admin_session_hours}h, Screen={self.screen_session_hours}h, User={self.user_session_hours}h"

