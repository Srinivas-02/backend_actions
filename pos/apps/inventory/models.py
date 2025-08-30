from django.db import models
from django.core.validators import MinValueValidator
from pydantic import ValidationError
from pos.apps.locations.models  import LocationModel

class Ingredient(models.Model):
    # add permissions checks 
    name = models.CharField(max_length=100,unique=True)
    unit = models.CharField(max_length=20)  # kg, L, pcs, etc.
    reorder_threshold = models.FloatField(validators=[MinValueValidator(0)])
    shelf_life = models.DurationField(null=True, blank=True)  # For perishables
    is_composite = models.BooleanField(default=False) # if it is made of raw materials (ex: dosa batter made of rice, urad dal, etc.)
    recipe_yield = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)]) # acts as a scale factor for composite ingredients
    recipe_ratios = models.JSONField(null=True, blank=True)  # {ingredient_id: ratio}

    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.name} ({self.unit})"
    
    class Meta:
        ordering = ['name']

class MasterIngredient(models.Model):

    UNIT_CHOICES = [

        ('kg', 'Kg'),
        ('g', 'Grams'),
        ('mg', 'Milligrams'),

        ('l', 'Liters'),
        ('ml', 'ML'),
        ('pcs', 'Pieces'),
        ('pack', 'Pack'),
        ('bottle', 'Bottle'),
        ('cup', 'Cup'),
        ('tbsp', 'Tablespoons'),
        ('tsp', 'Teaspoons'),

        ('dozen', 'Dozen'),
        ('bottle', 'Bottle'),
        ('bag', 'Bag'),

        ]
     
    # Master ingredients are not location-specific, they are global
    name = models.CharField(max_length=100, unique=True)
    unit = models.CharField(max_length=20)  # kg, L, pcs, etc.
    reorder_threshold = models.FloatField(validators=[MinValueValidator(0)])
    shelf_life = models.DurationField(null=True, blank=True)  # For perishables
    is_composite = models.BooleanField(default=False)  # if it is made of raw materials (ex: dosa batter made of rice, urad dal, etc.)
    recipe_yield = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)])  # acts as a scale factor for composite ingredients
    recipe_ratios = models.JSONField(null=True, blank=True)  # {ingredient_id: ratio}
    is_active = models.BooleanField(default=True)  # for soft deletion

    def clean(self):
        if self.is_composite and self.recipe_ratios:
            for key in self.recipe_ratios.keys():
                if not str(key).isdigit():   # 👈 ensures IDs, not names
                    raise ValidationError("Recipe ratios must use master ingredient IDs as keys, not names.")

    def __str__(self):
        return f"{self.name} ({self.unit})"
    
    class Meta:
        ordering = ['name']
        constraints = [
            models.CheckConstraint(check=models.Q(reorder_threshold__gte=0), name='reorder_threshold_non_negative'),
            models.CheckConstraint(
                check=models.Q(is_composite=False) | models.Q(recipe_yield__gt=0), 
                name='composite_recipe_yield_positive'
            ),
        ]

class LocationIngredient(models.Model):
    master_ingredient = models.ForeignKey(MasterIngredient, on_delete=models.CASCADE,related_name='location_ingredients')
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE)
    is_available = models.BooleanField(default=True)
    is_assigned = models.BooleanField(default=True)
    # Optional per-location overrides
    # reorder_threshold_override = models.FloatField(null=True, blank=True)
    # shelf_life_override = models.DurationField(null=True, blank=True)
    # recipe_ratios_override = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ('master_ingredient', 'location')

    def __str__(self):
        return f"{self.master_ingredient.name} @ {self.location.name}"


class DailyInventory(models.Model):
    date = models.DateField()
    location_ingredient = models.ForeignKey(LocationIngredient, on_delete=models.CASCADE, null=True, blank=True)
    opening_stock = models.FloatField(default=0,validators=[MinValueValidator(0)])
    prepared_qty = models.FloatField(default=0,validators=[MinValueValidator(0)])  # For composite item
    used_qty = models.FloatField(default=0,validators=[MinValueValidator(0)])
    closing_stock = models.FloatField(default=0,validators=[MinValueValidator(0)])
    # Auto-calculated only for composite ingredients
    raw_equiv = models.JSONField(null=True, blank=True)  # For composite items only
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE,)
    
    # Keep the old field temporarily for migration
    ingredient = models.ForeignKey('Ingredient', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['date', 'location_ingredient'], name='unique_daily_inventory'),
            models.CheckConstraint(check=models.Q(opening_stock__gte=0), name='opening_stock_non_negative'),
            models.CheckConstraint(check=models.Q(used_qty__gte=0), name='used_qty_non_negative'),
            models.CheckConstraint(check=models.Q(prepared_qty__gte=0), name='prepared_qty_non_negative'),
        ]

    def __str__(self):
        return f"{self.location_ingredient.master_ingredient.name} - {self.date}"
    
    
    
    class Meta:
        unique_together = ('date', 'location_ingredient', 'location')
        ordering = ['-date', 'location_ingredient__master_ingredient__name']


class PurchaseList(models.Model):

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ]
    
    date = models.DateField()
    location = models.ForeignKey(LocationModel,on_delete=models.CASCADE)
    created_by = models.CharField(max_length=20,blank=True,null=True) # chef,staff etc
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, null=True)  

    def __str__(self):
        return f"Purchase List #{self.id} - {self.location.name} - {self.date} - {self.status}"
    
    class Meta:
        ordering = ['-date']


class PurchaseListItem(models.Model):
    purchase_list = models.ForeignKey(PurchaseList, related_name='items', on_delete=models.CASCADE)
    location_ingredient = models.ForeignKey(LocationIngredient, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.FloatField(validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True, null=True)  
    
    # Keep the old field temporarily for migration
    ingredient = models.ForeignKey('Ingredient', on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        if self.location_ingredient:
            return f"{self.location_ingredient.master_ingredient.name} - {self.quantity} {self.location_ingredient.master_ingredient.unit} for {self.purchase_list.date}"
        elif self.ingredient:
            return f"{self.ingredient.name} - {self.quantity} {self.ingredient.unit} for {self.purchase_list.date}"
        return f"Item {self.id} for {self.purchase_list.date}"
    
    class Meta:
        unique_together = ('purchase_list', 'location_ingredient') # prevents adding same ingredient twice in the same purchase list
        ordering = ['location_ingredient__master_ingredient__name']
        constraints = [
            models.CheckConstraint(check=models.Q(quantity__gt=0), name='purchase_list_quantity_positive'),
        ]



class PurchaseEntry(models.Model):
   
    date = models.DateField()
    location_ingredient = models.ForeignKey(LocationIngredient, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.FloatField(validators=[MinValueValidator(0)])
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE)
    added_by = models.CharField(max_length=100)  # chef,staff,admin 
    
    # Keep the old field temporarily for migration
    ingredient = models.ForeignKey('Ingredient', on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        if self.location_ingredient:
            return f"{self.location_ingredient.master_ingredient.name} - {self.quantity} {self.location_ingredient.master_ingredient.unit} on {self.date}"
        elif self.ingredient:
            return f"{self.ingredient.name} - {self.quantity} {self.ingredient.unit} on {self.date}"
        return f"Entry {self.id} on {self.date}"

    class Meta:
        ordering = ['-date', 'location_ingredient__master_ingredient__name']
        constraints = [
            models.CheckConstraint(check=models.Q(quantity__gt=0), name='purchase_quantity_positive'),
        ]

