# menu/models.py
from django.db import models
from pos.apps.locations.models import LocationModel

class CategoryModel(models.Model):
    """Simple food categories like Breakfast, Coffee, Meals, etc."""
    name = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=0)
    image = models.BinaryField(null=True, blank=True)
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE)
    description = models.TextField(blank=True, null=True)  
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['display_order']

    def __str__(self):
        return self.name

class MenuItemModel(models.Model):
    """Basic menu items that can be ordered"""
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(CategoryModel, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=True)
    image = models.BinaryField(null=True, blank=True)
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['category__display_order', 'name']

    def __str__(self):
        return f"{self.name} - ₹{self.price}"



class MasterMenuCategory(models.Model):
    """Brand-wide categories: e.g. Coffee, Breakfast"""
    name = models.CharField(max_length=100)
    image = models.BinaryField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True) 

    class Meta:
        verbose_name_plural = "Categories"
      

    def __str__(self):
        return self.name

class MasterMenuItem(models.Model):
    """Brand-wide menu items (controlled by super admin)"""
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(MasterMenuCategory, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True) # for soft deletion
    image = models.BinaryField(null=True, blank=True)
    
    class Meta:
        ordering = [ 'name']

    def __str__(self):
        return f"{self.name} - ₹{self.price}"


class LocationMenuItem(models.Model):
    """Location-specific menu items """
    menu_item = models.ForeignKey(MasterMenuItem, on_delete=models.CASCADE, related_name='location_items')
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True) # if we want to allow location-specific pricing
    is_available = models.BooleanField(default=True)
    is_assigned = models.BooleanField(default=True)  # if this item is assigned to the location

    class Meta:
        unique_together = ('menu_item', 'location')
        ordering = [ 'menu_item__name']
    def __str__(self):
        return f"{self.menu_item.name} ({self.location.name}) - {'Available' if self.is_available else 'Not Available'}"

class LocationMenuCategory(models.Model):
    """Location-specific categories"""
    category = models.ForeignKey(MasterMenuCategory, on_delete=models.CASCADE, related_name='location_categories')
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=True)
    is_assigned = models.BooleanField(default=True)  # if this category is assigned to the location

    class Meta:
        unique_together = ('category', 'location')

    def __str__(self):
        return f"{self.category.name} ({self.location.name})"