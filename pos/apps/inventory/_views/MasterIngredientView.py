from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from pos.apps.inventory.models import LocationIngredient, MasterIngredient
from django.shortcuts import get_object_or_404
from datetime import timedelta

class MasterIngredientView(APIView):
    def get(self, request, pk=None):

        if pk:
            ingredient = get_object_or_404(MasterIngredient, id=pk)
            data = {
                'id': ingredient.id,
                'name': ingredient.name,
                'unit': ingredient.unit,
                'reorder_threshold': ingredient.reorder_threshold,
                'shelf_life': str(ingredient.shelf_life) if ingredient.shelf_life else None,
                'is_composite': ingredient.is_composite,
                'recipe_yield': ingredient.recipe_yield,
                'recipe_ratios': self._get_readable_ratios(ingredient.recipe_ratios) if ingredient.is_composite else None,
                'is_active': ingredient.is_active
            }
            return Response({'status': 'success', 'data': data}, status=status.HTTP_200_OK)
        else:
            ingredients = MasterIngredient.objects.filter(is_active=True)
            if not ingredients:
                return Response({'status': 'success', 'data': []}, status=status.HTTP_200_OK)
            data = []
            for item in ingredients:
                data.append({
                    'id': item.id,
                    'name': item.name,
                    'unit': item.unit,
                    'reorder_threshold': item.reorder_threshold,
                    'shelf_life': str(item.shelf_life) if item.shelf_life else None,
                    'is_composite': item.is_composite,
                    'recipe_yield': item.recipe_yield,
                    'recipe_ratios': self._get_readable_ratios(item.recipe_ratios) if item.is_composite else None,
                    'is_active': item.is_active
                })
            return Response({'status': 'success', 'data': data}, status=status.HTTP_200_OK)

    def post(self, request):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'not allowed'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        try:
            name = data.get("name", "").strip().lower()
            if MasterIngredient.objects.filter(name__iexact=name).exists():
                return Response({
                    "status": "error",
                    "message": f"Ingredient with name '{name}' already exists"
                }, status=400)

            shelf_life = timedelta(hours=int(data["shelf_life"])) if data.get("shelf_life") else None
            recipe_ratios = data.get("recipe_ratios", {})

            if data.get("is_composite", False):
                if not isinstance(recipe_ratios, dict):
                    return Response({'status': 'error', 'message': 'recipe_ratios must be a dictionary'}, status=400)
                invalid_ids = [raw_id for raw_id in recipe_ratios if not MasterIngredient.objects.filter(id=raw_id).exists()]
                if invalid_ids:
                    return Response({'status': 'error', 'message': f'Invalid ingredient IDs in recipe_ratios: {invalid_ids}'}, status=400)

            ingredient = MasterIngredient.objects.create(
                name=name,
                unit=data.get("unit"),
                reorder_threshold=data.get("reorder_threshold", 0),
                shelf_life=shelf_life,
                is_composite=data.get("is_composite", False),
                recipe_yield=data.get("recipe_yield"),
                recipe_ratios=recipe_ratios if data.get("is_composite", False) else None
            )

            return Response({
                'status': 'success',
                'id': ingredient.id,
                'name': ingredient.name,
                'unit': ingredient.unit,
                'reorder_threshold': ingredient.reorder_threshold,
                'shelf_life': str(ingredient.shelf_life) if ingredient.shelf_life else None,
                'is_composite': ingredient.is_composite,
                'recipe_yield': ingredient.recipe_yield,
                'recipe_ratios': self._get_readable_ratios(ingredient.recipe_ratios) if ingredient.is_composite else None
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'not allowed'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        ingredient_id = pk or data.get("id")
        try:
            # Get the ingredient first
            ingredient = get_object_or_404(MasterIngredient, id=ingredient_id)
            
            if "name" in data:
                new_name = str(data["name"]).strip()
                # Check for duplicate names (case-insensitive), excluding current ingredient
                if MasterIngredient.objects.filter(name__iexact=new_name).exclude(id=ingredient.id).exists():
                    return Response({'status': 'error', 'message': f"Ingredient with name '{new_name}' already exists"}, status=400)
                ingredient.name = new_name

            if "unit" in data:
                ingredient.unit = str(data["unit"]).strip()

            if "reorder_threshold" in data:
                try:
                    ingredient.reorder_threshold = float(data["reorder_threshold"])
                except (ValueError, TypeError):
                    return Response({'status': 'error', 'message': 'reorder_threshold must be a number'}, status=400)

            if "shelf_life" in data:
                try:
                    ingredient.shelf_life = timedelta(hours=int(data["shelf_life"])) if data["shelf_life"] else None
                except (ValueError, TypeError):
                    return Response({'status': 'error', 'message': 'shelf_life must be an integer (hours) or null'}, status=400)

            if "is_composite" in data:
                ingredient.is_composite = bool(data["is_composite"])

            if ingredient.is_composite:
                if "recipe_yield" in data:
                    try:
                        ingredient.recipe_yield = float(data["recipe_yield"])
                    except (ValueError, TypeError):
                        return Response({'status': 'error', 'message': 'recipe_yield must be a number'}, status=400)
                if "recipe_ratios" in data:
                    recipe_ratios = data["recipe_ratios"]
                    if not isinstance(recipe_ratios, dict):
                        return Response({'status': 'error', 'message': 'recipe_ratios must be a dictionary'}, status=400)
                    invalid_ids = []
                    for raw_id in recipe_ratios:
                        try:
                            raw_id_int = int(raw_id)
                        except (ValueError, TypeError):
                            invalid_ids.append(raw_id)
                            continue
                        if not MasterIngredient.objects.filter(id=raw_id_int, is_active=True).exists():
                            invalid_ids.append(raw_id)
                    if invalid_ids:
                        return Response({'status': 'error', 'message': f'Invalid ingredient IDs in recipe_ratios: {invalid_ids}'}, status=400)
                    # Optionally cast keys to str for consistency
                    ingredient.recipe_ratios = {str(k): v for k, v in recipe_ratios.items()}
            else:
                ingredient.recipe_yield = None
                ingredient.recipe_ratios = None

            ingredient.save()

            return Response({
                'status': 'success',
                'id': ingredient.id,
                'name': ingredient.name,
                'unit': ingredient.unit,
                'reorder_threshold': ingredient.reorder_threshold,
                'shelf_life': str(ingredient.shelf_life) if ingredient.shelf_life else None,
                'is_composite': ingredient.is_composite,
                'recipe_yield': ingredient.recipe_yield,
                'recipe_ratios': self._get_readable_ratios(ingredient.recipe_ratios) if ingredient.recipe_ratios else None
            }, status=200)

        except Exception as e:
            import traceback
            return Response({'status': 'error', 'message': f'{type(e).__name__}: {str(e)}', 'trace': traceback.format_exc()}, status=400)
        
    def delete(self, request, pk=None):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Not allowed'}, status=status.HTTP_403_FORBIDDEN)

        ingredient_id = pk or request.data.get("id")
        if not ingredient_id:
            return Response({'status': 'error', 'message': 'Ingredient ID is required'}, status=400)

        ingredient = get_object_or_404(MasterIngredient, id=ingredient_id)

        # Restrict deleting composite ingredients that still have recipe ratios
        if ingredient.is_composite and ingredient.recipe_ratios:
            return Response({
                'status': 'error',
                'message': f"Cannot delete composite ingredient '{ingredient.name}' because it still has recipe ratios. "
                           f"Please remove all recipe ratios first."
            }, status=status.HTTP_400_BAD_REQUEST)

        #  Restrict deleting if this ingredient is used in other composites
        used_in = MasterIngredient.objects.filter(
            is_active=True,
            is_composite=True,
            recipe_ratios__has_key=str(ingredient_id)
        )
        if used_in.exists():
            used_in_names = ", ".join(used_in.values_list('name', flat=True))
            return Response({
                'status': 'error',
                'message': f"Cannot delete '{ingredient.name}' because it is used in the recipe of: {used_in_names}. "
                           f"Please update their recipe_ratios first."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Proceed to soft delete 
        try:
            with transaction.atomic():
                # soft delete 
                ingredient.is_active = False
                ingredient.save(update_fields=["is_active"])

                #  unassign and make this ingredient unavailable for all locations
                updated_count = LocationIngredient.objects.filter(
                    master_ingredient=ingredient
                ).update(is_assigned=False, is_available=False)

            return Response({
                'status': 'success',
                'message': f"Ingredient '{ingredient.name}' soft deleted successfully",
                'unassigned_locations': updated_count
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _get_readable_ratios(self, recipe_ratios):
        if not recipe_ratios:
            return None
        readable = []
        for raw_id, ratio in recipe_ratios.items():
            try:
                raw_ingredient = MasterIngredient.objects.get(id=int(raw_id))
                readable.append({"id": raw_ingredient.id, "name": raw_ingredient.name, "ratio": ratio})
            except MasterIngredient.DoesNotExist:
                continue
        return readable
