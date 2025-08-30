from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.inventory.models import LocationIngredient, MasterIngredient
from pos.apps.locations.models import LocationModel
from pos.apps.utils import  ensure_can_access_location
from django.shortcuts import get_object_or_404
from django.db import transaction
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

def get_recipe_ratios_display(recipe_ratios):
    if not recipe_ratios:
        return None

    ingredient_ids = recipe_ratios.keys()
    ingredients = MasterIngredient.objects.filter(pk__in=ingredient_ids)
    found_ids = set(str(ing.id) for ing in ingredients)
    missing_ids = set(str(ing_id) for ing_id in ingredient_ids) - found_ids

    if missing_ids:
        raise ValueError(f"Invalid MasterIngredient IDs in recipe_ratios: {', '.join(missing_ids)}")

    # Create map {id: {"name": ..., "ratio": ...}}
    ingredient_map = {
        str(ing.id): {
            "ingredient_name": ing.name,
            "ratio": recipe_ratios[str(ing.id)]
        }
        for ing in ingredients
    }

    return ingredient_map
class LocationIngredientView(APIView):
    """
    Super Admin:
        Bulk-assign ingredients to a location (POST)
        Bulk-update availability (PATCH)
        Unassign (DELETE)
        Read any assignment (GET)
    Franchise Admin:
        Read assignment rows for their own locations only (GET)
    """

    def get(self, request, pk=None):
        """
        List assignments for a location or retrieve a single assignment row.

        Query params for list:
        - location_id (required)
        - assigned: "true" (default) or "false"
        """
        if pk:
            location_ingredient = get_object_or_404(
                LocationIngredient.objects.select_related('master_ingredient', 'location'),
                pk=pk,
                master_ingredient__is_active=True
            )

            # Permission check
            if not ensure_can_access_location(request.user, location_ingredient.location_id):
                return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

            master = location_ingredient.master_ingredient
            return Response({
                'id': location_ingredient.id,
                'master_ingredient_id': master.id,
                'master_ingredient_name': master.name,
                'master_ingredient_unit': master.unit,
                'master_ingredient_reorder_threshold': master.reorder_threshold,
                'master_ingredient_shelf_life': str(master.shelf_life) if master.shelf_life else None,
                'master_ingredient_is_composite': master.is_composite,
                'master_ingredient_recipe_yield': master.recipe_yield,
                'master_ingredient_recipe_ratios': (
                    get_recipe_ratios_display(master.recipe_ratios) if master.is_composite else None
                ),
                'location_id': location_ingredient.location.id,
                'location_name': location_ingredient.location.name,
                'is_assigned': getattr(location_ingredient, 'is_assigned', True),
                'is_available': location_ingredient.is_available,
            }, status=status.HTTP_200_OK)

        location_id = request.query_params.get('location_id')
        if not location_id:
            return Response({'error': 'location_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if not ensure_can_access_location(request.user, location_id):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        queryset = LocationIngredient.objects.select_related('master_ingredient', 'location')\
            .filter(location_id=location_id, master_ingredient__is_active=True)

        # Assigned filter (default = true)
        assigned_param = request.query_params.get('assigned')
        if assigned_param is None or assigned_param.lower() == 'true':
            queryset = queryset.filter(is_assigned=True)
        elif assigned_param.lower() == 'false':
            queryset = queryset.filter(is_assigned=False)

        data = []
        for item in queryset:
            master = item.master_ingredient
            data.append({
                'id': item.id,
                'master_ingredient_id': master.id,
                'master_ingredient_name': master.name,
                'master_ingredient_unit': master.unit,
                'master_ingredient_reorder_threshold': master.reorder_threshold,
                'master_ingredient_shelf_life': str(master.shelf_life) if master.shelf_life else None,
                'master_ingredient_is_composite': master.is_composite,
                'master_ingredient_recipe_yield': master.recipe_yield,
                'master_ingredient_recipe_ratios': (
                    get_recipe_ratios_display(master.recipe_ratios) if master.is_composite else None
                ),
                'location_id': item.location.id,
                'location_name': item.location.name,
                'is_assigned': getattr(item, 'is_assigned', True),
                'is_available': item.is_available,
            })

        return Response({'location_ingredients': data}, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Bulk assign ingredients to a location (no de-duplication).
        - If the row exists: set is_assigned=True and is_available from the payload.
        - If it does not exist: create it with is_assigned=True and is_available from the payload.
        - For composite ingredients: automatically assigns all required raw ingredients.
        """
        location_id = request.data.get('location_id')
        ingredients_payload = request.data.get('ingredients', [])

        if not location_id or not ingredients_payload:
            return Response({'error': 'location_id and ingredients are required'}, status=400)

        # Permission guard: super admin → any location; franchise admin → only their locations
        if not ensure_can_access_location(request.user, location_id):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        location = get_object_or_404(LocationModel, pk=location_id)

        results = []
        with transaction.atomic():
            # Keep track of all ingredients to assign (including auto-assigned raw ingredients)
            ingredients_to_assign = {}
            
            # First pass: collect all requested ingredients and their raw dependencies
            for ingredient_input in ingredients_payload:
                master_ingredient_id = ingredient_input.get('id')
                if master_ingredient_id is None:
                    # Skip invalid entries instead of failing the whole request
                    continue

                requested_is_available = bool(ingredient_input.get('is_available', True))
                
                # Only assign active master ingredients
                try:
                    master_ingredient = MasterIngredient.objects.get(pk=master_ingredient_id, is_active=True)
                except MasterIngredient.DoesNotExist:
                    continue
                
                # Add the requested ingredient
                ingredients_to_assign[master_ingredient_id] = {
                    'ingredient': master_ingredient,
                    'is_available': requested_is_available,
                    'explicitly_requested': True
                }
                
                # If it's composite, add all raw ingredients required
                if master_ingredient.is_composite and master_ingredient.recipe_ratios:
                    raw_ingredient_ids = master_ingredient.recipe_ratios.keys()
                    
                    # Fetch all raw ingredients
                    raw_ingredients = MasterIngredient.objects.filter(
                        pk__in=raw_ingredient_ids, 
                        is_active=True
                    )
                    
                    # Check if all required raw ingredients exist
                    found_ids = {str(ing.id) for ing in raw_ingredients}
                    missing_ids = set(str(ing_id) for ing_id in raw_ingredient_ids) - found_ids
                    
                    if missing_ids:
                        return Response({
                            'error': f"Cannot assign composite ingredient '{master_ingredient.name}' because the following raw ingredients are missing or inactive: {', '.join(missing_ids)}"
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Add raw ingredients (if not already requested explicitly)
                    for raw_ingredient in raw_ingredients:
                        if raw_ingredient.id not in ingredients_to_assign:
                            ingredients_to_assign[raw_ingredient.id] = {
                                'ingredient': raw_ingredient,
                                'is_available': True,  # Default to available for auto-assigned ingredients
                                'explicitly_requested': False
                            }

            # Second pass: assign all ingredients
            for ingredient_id, ingredient_data in ingredients_to_assign.items():
                master_ingredient = ingredient_data['ingredient']
                requested_is_available = ingredient_data['is_available']
                
                # Create or update the (master, location) pair
                location_ingredient, created = LocationIngredient.objects.update_or_create(
                    master_ingredient=master_ingredient,
                    location=location,
                    defaults={
                        'is_assigned': True,
                        'is_available': requested_is_available,
                    }
                )

                results.append({
                    'id': location_ingredient.id,
                    'master_ingredient_id': master_ingredient.id,
                    'master_ingredient_name': master_ingredient.name,
                    'master_ingredient_unit': master_ingredient.unit,
                    'master_ingredient_reorder_threshold': master_ingredient.reorder_threshold,
                    'master_ingredient_shelf_life': str(master_ingredient.shelf_life) if master_ingredient.shelf_life else None,
                    'master_ingredient_is_composite': master_ingredient.is_composite,
                    'master_ingredient_recipe_yield': master_ingredient.recipe_yield,
                    'master_ingredient_recipe_ratios': (
                        get_recipe_ratios_display(master_ingredient.recipe_ratios)
                        if master_ingredient.is_composite else None
                    ),
                    'location_id': location.id,
                    'location_name': location.name,
                    'is_assigned': location_ingredient.is_assigned,
                    'is_available': location_ingredient.is_available,
                    'explicitly_requested': ingredient_data['explicitly_requested'],
                    'auto_assigned': not ingredient_data['explicitly_requested'],
                })

        return Response({'status': 'success', 'data': results}, status=status.HTTP_201_CREATED)
    
    def patch(self, request, pk=None):
        """
        Toggle the is_available flag for assigned ingredients.
        Does not change is_assigned status.
        Validates that composite ingredients can only be made available if all raw ingredients are available.
        """

        ingredients_payload = request.data.get('ingredients', [])
        if not ingredients_payload:
            return Response({'error': 'ingredients are required'}, status=status.HTTP_400_BAD_REQUEST)

        updated = []
        errors = []
        
        with transaction.atomic():
            for ingredient_object in ingredients_payload:
                location_ingredient_id = ingredient_object.get('id')
                is_available = ingredient_object.get('is_available')

                if location_ingredient_id is None or is_available is None:
                    continue

                try:
                    location_ingredient = LocationIngredient.objects.select_related('master_ingredient').get(
                        id=location_ingredient_id,
                        is_assigned=True  # ensure it's assigned before toggling availability
                    )
                except LocationIngredient.DoesNotExist:
                    continue

                # If trying to make a composite ingredient available, validate raw ingredients
                if (is_available and 
                    location_ingredient.master_ingredient.is_composite and 
                    location_ingredient.master_ingredient.recipe_ratios):
                    
                    raw_ingredient_ids = location_ingredient.master_ingredient.recipe_ratios.keys()
                    missing_raw_ingredients = []
                    
                    for raw_id in raw_ingredient_ids:
                        try:
                            raw_location_ingredient = LocationIngredient.objects.get(
                                master_ingredient_id=raw_id,
                                location=location_ingredient.location,
                                is_assigned=True
                            )
                            if not raw_location_ingredient.is_available:
                                missing_raw_ingredients.append(raw_location_ingredient.master_ingredient.name)
                        except LocationIngredient.DoesNotExist:
                            # Raw ingredient not assigned to location
                            try:
                                raw_ingredient = MasterIngredient.objects.get(pk=raw_id, is_active=True)
                                missing_raw_ingredients.append(f"{raw_ingredient.name} (not assigned)")
                            except MasterIngredient.DoesNotExist:
                                missing_raw_ingredients.append(f"Unknown ingredient (ID: {raw_id})")
                    
                    if missing_raw_ingredients:
                        errors.append({
                            'ingredient_name': location_ingredient.master_ingredient.name,
                            'error': f"Cannot make composite ingredient available. Missing or unavailable raw ingredients: {', '.join(missing_raw_ingredients)}"
                        })
                        continue

                # If trying to make a raw ingredient unavailable, check if it's used by available composites
                if (not is_available and 
                    not location_ingredient.master_ingredient.is_composite):
                    
                    dependent_composites = LocationIngredient.objects.filter(
                        location=location_ingredient.location,
                        is_assigned=True,
                        is_available=True,
                        master_ingredient__is_composite=True,
                        master_ingredient__recipe_ratios__has_key=str(location_ingredient.master_ingredient.id)
                    )
                    
                    if dependent_composites.exists():
                        dependent_names = ", ".join(
                            dependent_composites.values_list('master_ingredient__name', flat=True)
                        )
                        errors.append({
                            'ingredient_name': location_ingredient.master_ingredient.name,
                            'error': f"Cannot make raw ingredient unavailable. It is required by available composite ingredients: {dependent_names}"
                        })
                        continue

                # Update the availability
                if location_ingredient.is_available != is_available:
                    location_ingredient.is_available = is_available
                    location_ingredient.save(update_fields=['is_available'])

                updated.append({
                    'id': location_ingredient.id,
                    'master_ingredient_id': location_ingredient.master_ingredient.id,
                    'master_ingredient_name': location_ingredient.master_ingredient.name,
                    'location_id': location_ingredient.location.id,
                    'location_name': location_ingredient.location.name,
                    'is_available': location_ingredient.is_available
                })

        response_data = {'status': 'success', 'data': updated}
        if errors:
            response_data['errors'] = errors
            response_data['status'] = 'partial_success' if updated else 'error'

        return Response(response_data, status=status.HTTP_200_OK)



    def delete(self, request, pk=None):
        """
        Unassign an ingredient from a location.
        - Sets is_assigned=False and is_available=False
        - Blocks if any assigned+available composite depends on it
        """
        location_ingredient_id = pk or request.data.get("id")
        if not location_ingredient_id:
            return Response({'status': 'error', 'message': 'Assignment ID required'}, status=400)

        location_ingredient = get_object_or_404(
            LocationIngredient.objects.select_related('location', 'master_ingredient'),
            id=location_ingredient_id
        )

        # Permission check
        if not ensure_can_access_location(request.user, location_ingredient.location_id):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        ingredient_id = location_ingredient.master_ingredient.id
        location = location_ingredient.location

        # check if this raw item is used in any of the composite ingredients
        dependent_composites = LocationIngredient.objects.filter(
            location=location,
            is_assigned=True,
            is_available=True,
            master_ingredient__is_composite=True,
            master_ingredient__recipe_ratios__has_key=str(ingredient_id)
        )

        if dependent_composites.exists():
            dependent_names = ", ".join(
                dependent_composites.values_list('master_ingredient__name', flat=True)
            )
            return Response({
                'status': 'error',
                'message': (
                    f"Cannot unassign '{location_ingredient.master_ingredient.name}' from location "
                    f"because it is used in the recipe of: {dependent_names}. "
                    f"Please unassign those first."
                )
            }, status=status.HTTP_400_BAD_REQUEST)

        # Soft-unassign
        with transaction.atomic():
            location_ingredient.is_assigned = False
            location_ingredient.is_available = False
            location_ingredient.save(update_fields=['is_assigned', 'is_available'])

        return Response(
            {
                'status': 'success',
                'message': f"Ingredient '{location_ingredient.master_ingredient.name}' unassigned successfully"
            },
            status=status.HTTP_200_OK
        )
