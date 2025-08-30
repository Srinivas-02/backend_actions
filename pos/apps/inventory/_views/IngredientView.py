from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.inventory.models import Ingredient, LocationModel
from django.shortcuts import get_object_or_404
from datetime import timedelta


class IngredientView(APIView):
    def get(self, request):
        ingredients = Ingredient.objects.all()

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
                'location': item.location.name,
                'location_id': item.location.id
            })

        return Response({'status': 'success', 'data': data}, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data
        try:
            name = data.get("name", "").strip().lower()

            if Ingredient.objects.filter(name__iexact=name).exists():
                return Response({
                    "status": "error",
                    "message": f"Ingredient with name '{name}' already exists"
                }, status=400)

            shelf_life = timedelta(hours=int(data["shelf_life"])) if data.get("shelf_life") else None

            recipe_ratios = data.get("recipe_ratios", {})

            if data.get("is_composite", False):
                if not isinstance(recipe_ratios, dict):
                    return Response({'status': 'error', 'message': 'recipe_ratios must be a dictionary'}, status=400)

                invalid_ids = [raw_id for raw_id in recipe_ratios if not Ingredient.objects.filter(id=raw_id).exists()]
                if invalid_ids:
                    return Response({'status': 'error', 'message': f'Invalid ingredient IDs in recipe_ratios: {invalid_ids}'}, status=400)

            location_id = data.get("location_id")
            if not location_id:
                return Response({'status': 'error', 'message': 'location_id is required'}, status=400)

            location = get_object_or_404(LocationModel, id=location_id)

            ingredient = Ingredient.objects.create(
                name=name,
                unit=data.get("unit"),
                reorder_threshold=data.get("reorder_threshold", 0),
                shelf_life=shelf_life,
                is_composite=data.get("is_composite", False),
                recipe_yield=data.get("recipe_yield"),
                recipe_ratios=recipe_ratios if data.get("is_composite", False) else None,
                location=location
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
                'recipe_ratios': self._get_readable_ratios(ingredient.recipe_ratios) if ingredient.is_composite else None,
                'location': ingredient.location.name,
                'location_id': ingredient.location.id
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        data = request.data
        try:
            ingredient_id = data.get("id")
            if not ingredient_id:
                return Response({'status': 'error', 'message': 'Ingredient ID is required'}, status=400)

            ingredient = get_object_or_404(Ingredient, id=ingredient_id)

            if "name" in data:
                ingredient.name = data["name"]

            if "unit" in data:
                ingredient.unit = data["unit"]

            if "reorder_threshold" in data:
                ingredient.reorder_threshold = float(data["reorder_threshold"])

            if "shelf_life" in data:
                ingredient.shelf_life = timedelta(hours=int(data["shelf_life"])) if data["shelf_life"] else None

            if "is_composite" in data:
                ingredient.is_composite = bool(data["is_composite"])

            if ingredient.is_composite:
                if "recipe_yield" in data:
                    ingredient.recipe_yield = float(data["recipe_yield"])
                if "recipe_ratios" in data:
                    recipe_ratios = data["recipe_ratios"]
                    if not isinstance(recipe_ratios, dict):
                        return Response({'status': 'error', 'message': 'recipe_ratios must be a dictionary'}, status=400)

                    invalid_ids = [raw_id for raw_id in recipe_ratios if not Ingredient.objects.filter(id=raw_id).exists()]
                    if invalid_ids:
                        return Response({'status': 'error', 'message': f'Invalid ingredient IDs in recipe_ratios: {invalid_ids}'}, status=400)

                    ingredient.recipe_ratios = recipe_ratios
            else:
                ingredient.recipe_yield = None
                ingredient.recipe_ratios = None

            if "location_id" in data:
                location = get_object_or_404(LocationModel, id=data["location_id"])
                ingredient.location = location

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
                'recipe_ratios': self._get_readable_ratios(ingredient.recipe_ratios) if ingredient.recipe_ratios else None,
                'location': ingredient.location.name,
                'location_id': ingredient.location.id
            }, status=200)

        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)

    def delete(self, request):
        id = request.data.get("id")
        try:
            ingredient = get_object_or_404(Ingredient, id=id)
            ingredient.delete()
            return Response({'status': 'success', 'message': 'Ingredient deleted successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _get_readable_ratios(self, recipe_ratios):
        if not recipe_ratios:
            return None

        readable = []
        for raw_id, ratio in recipe_ratios.items():
            try:
                raw_ingredient = Ingredient.objects.get(id=int(raw_id))
                readable.append({"id": raw_ingredient.id, "name": raw_ingredient.name, "ratio": ratio})
            except Ingredient.DoesNotExist:
                continue
        return readable
