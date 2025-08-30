# accounts/models.py
from django.db import models
from django.utils import timezone

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """Creates and saves a regular user with the given email and password"""
        if not email:
            raise ValueError('Users must have an email address')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """Creates and saves a superadmin with the given email and password"""
        extra_fields.setdefault('is_super_admin', True)
        
        if extra_fields.get('is_super_admin') is not True:
            raise ValueError('Superuser must have is_super_admin=True')
        
        return self.create_user(email, password, **extra_fields)

    def create_staff_user(self, email, password, locations=None, **extra_fields):
        """Creates and saves a staff member with the given email, password and locations"""
        extra_fields.setdefault('is_staff_member', True)
        
        if extra_fields.get('is_staff_member') is not True:
            raise ValueError('Staff user must have is_staff_member=True')
        
        user = self.create_user(email, password, **extra_fields)
        
        if locations:
            user.locations.set(locations)
            
        return user
 
class User(AbstractBaseUser):
    email = models.EmailField('email address', unique=True)
    first_name = models.CharField('first name', max_length=100)
    last_name = models.CharField('last name', max_length=100)

    is_super_admin = models.BooleanField('super admin status', default=False)
    is_franchise_admin = models.BooleanField('franchise admin status', default=False)
    is_staff_member = models.BooleanField('staff member status', default=False)

    locations = models.ManyToManyField('locations.LocationModel', blank=True)

    is_logged_in = models.BooleanField(default=False)
    created_by = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='created_users')

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def has_location_access(self, location_id):
        """Check if user has access to a specific location"""
        if self.is_super_admin:
            return True
        return self.locations.filter(id=location_id).exists()
    
    def save(self, *args, **kwargs):
        """Ensure role consistency on save"""
        if sum([self.is_super_admin, self.is_franchise_admin, self.is_staff_member]) > 1:
            raise ValueError("User can only have one role at a time")
        
        super().save(*args, **kwargs)


class BlacklistedToken(models.Model):
    jti = models.CharField(max_length=255, unique=True)
    token = models.TextField(null=True, blank=True)  # Optional: store token for debugging
    blacklisted_on = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Blacklisted Token"
        verbose_name_plural = "Blacklisted Tokens"
        indexes = [
            models.Index(fields=["jti"]),
        ]
    
    def __str__(self):
        return f"Blacklisted on {self.blacklisted_on.strftime('%Y-%m-%d %H:%M:%S')} | Token ID: {self.jti}"