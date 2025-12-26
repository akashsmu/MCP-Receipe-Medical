#!/usr/bin/env python3
"""
LogMeal API client for food recognition and nutrition analysis with URL support.
"""

import os
import base64
import requests
import logging
from typing import Dict, Any, List, Optional
from PIL import Image
import io

logger = logging.getLogger("mcp_recipe_server.logmeal")


class LogMealClient:
    """Client for interacting with LogMeal API."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.logmeal.com/v2"):
        """
        Initialize LogMeal client.
        
        Args:
            api_key: LogMeal API key
            base_url: LogMeal API base URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        logger.info("LogMeal client initialized")

    def _encode_image(self, image_path: str) -> Optional[str]:
        """
        Encode image to base64 string.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64 encoded image string or None if error
        """
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if image is too large (LogMeal has size limits)
                max_size = (800, 800)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Convert to base64
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=85)
                buffer.seek(0)
                image_bytes = buffer.getvalue()
                
                return base64.b64encode(image_bytes).decode('utf-8')
                
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            return None

    def _process_base64_image(self, image_base64: str) -> Dict[str, Any]:
        """
        Process base64 encoded image for LogMeal API.
        
        Args:
            image_base64: Base64 encoded image string
            
        Returns:
            API response
        """
        try:
            url = f"{self.base_url}/image/segmentation/complete"
            
            # Decode base64 to bytes for multipart upload
            image_bytes = base64.b64decode(image_base64)
            
            # Prepare headers (exclude Content-Type to let requests handle boundary)
            headers = {
                'Authorization': self.headers['Authorization']
            }
            
            # Send as multipart/form-data
            files = {
                'image': ('image.jpg', image_bytes, 'image/jpeg')
            }
            
            response = requests.post(url, files=files, headers=headers)
            
            # Check for error response first
            if not response.ok:
                logger.error(f"API Error Response: {response.text}")
            
            response.raise_for_status()
            
            result = response.json()
            return {
                "success": True,
                "recognition_results": result.get('recognition_results', []),
                "segmentation_results": result.get('segmentation_results', []),
                "image_analysis_id": result.get('image_analysis_id'),
                "raw_response": result # helpful for debugging
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LogMeal API request failed: {e}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Food recognition failed: {e}")
            return {
                "success": False,
                "error": f"Recognition failed: {str(e)}"
            }

    def recognize_food(self, image_path: str) -> Dict[str, Any]:
        """
        Recognize food items in an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Recognition results
        """
        try:
            logger.info(f"Recognizing food in image: {image_path}")
            
            # Encode image
            image_data = self._encode_image(image_path)
            if not image_data:
                return {
                    "success": False,
                    "error": "Failed to process image"
                }
            
            return self._process_base64_image(image_data)
            
        except Exception as e:
            logger.error(f"Food recognition failed: {e}")
            return {
                "success": False,
                "error": f"Recognition failed: {str(e)}"
            }

    def recognize_food_from_base64(self, image_base64: str) -> Dict[str, Any]:
        """
        Recognize food items from base64 encoded image.
        
        Args:
            image_base64: Base64 encoded image string
            
        Returns:
            Recognition results
        """
        logger.info("Recognizing food from base64 encoded image")
        return self._process_base64_image(image_base64)

    def get_recipe_ingredients(self, recipe_id: str) -> Dict[str, Any]:
        """
        Get ingredients for a specific recipe by ID.
        
        Args:
            recipe_id: The ID of the recipe/dish
            
        Returns:
            Dictionary containing ingredient details
        """
        try:
            logger.info(f"Getting ingredients for recipe ID: {recipe_id}")
            
            url = f"{self.base_url}/nutrition/recipe/ingredients"
            payload = {
                "id": recipe_id
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            result = response.json()
            return {
                "success": True,
                "recipe_id": recipe_id,
                "ingredients": result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Recipe ingredients request failed: {e}")
            return {
                "success": False,
                "error": f"Failed to get ingredients: {str(e)}"
            }

    def _extract_top_food_item(self, segmentation_results: List[Dict]) -> Optional[Dict]:
        """
        Extract the food item with the highest probability from nested segmentation results.
        
        Args:
            segmentation_results: List of segmentation result dictionaries
            
        Returns:
            Dictionary of the best match item or None
        """
        best_item = None
        highest_prob = -1.0
        
        # Helper to recursively search for best candidate
        def check_candidates(candidates):
            nonlocal best_item, highest_prob
            for candidate in candidates:
                # Check current candidate
                prob = candidate.get('prob', 0)
                if prob > highest_prob:
                    highest_prob = prob
                    best_item = candidate
                
                # Check subclasses if they exist (sometimes more specific matches are nested)
                if 'subclasses' in candidate and candidate['subclasses']:
                    check_candidates(candidate['subclasses'])

        # Start search
        for segment in segmentation_results:
            if 'recognition_results' in segment:
                check_candidates(segment['recognition_results'])
        
        return best_item

    def analyze_food_image(self, image_path: str) -> Dict[str, Any]:
        """
        Complete analysis: recognize food, find best match, and get ingredients.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Complete analysis results
        """
        # First recognize food items (segmentation)
        recognition_response = self.recognize_food(image_path)
        if not recognition_response["success"]:
            return recognition_response
        
        # Extract segmentation results (handling both direct and nested keys if API varies)
        segmentation_results = recognition_response.get("recognition_results", [])
        if not segmentation_results and "segmentation_results" in recognition_response:
             segmentation_results = recognition_response["segmentation_results"]
             
        # Find best match
        best_item = self._extract_top_food_item(segmentation_results)
        
        if not best_item:
            return {
                "success": True,
                "recognized_dish": None,
                "message": "No specific food items recognized with sufficient confidence"
            }
            
        logger.info(f"Top detection: {best_item.get('name')} ({best_item.get('prob', 0):.2f})")
        
        # Get ingredients for this specific dish
        ingredients_result = {}
        if 'id' in best_item:
            ingredients_result = self.get_recipe_ingredients(best_item['id'])
        
        return {
            "success": True,
            "recognized_dish": {
                "name": best_item.get('name'),
                "id": best_item.get('id'),
                "confidence": best_item.get('prob'),
                "food_family": best_item.get('foodFamily', [])
            },
            "ingredients_info": ingredients_result.get("ingredients", {}) if ingredients_result.get("success") else {},
            "image_analysis_id": recognition_response.get("image_analysis_id")
        }

    def analyze_food_from_base64(self, image_base64: str) -> Dict[str, Any]:
        """
        Complete analysis: recognize food, find best match, and get ingredients from base64.
        
        Args:
            image_base64: Base64 encoded image string
            
        Returns:
            Complete analysis results
        """
        # First recognize food items
        recognition_response = self.recognize_food_from_base64(image_base64)
        if not recognition_response["success"]:
            return recognition_response
        
        # Extract segmentation results (robust checking)
        segmentation_results = recognition_response.get("recognition_results", [])
        # In the provided sample, 'segmentation_results' is at top level
        # But our client _process_base64_image currently puts raw JSON into 'recognition_results' key 
        # Wait, check _process_base64_image implementation:
        # It returns {"recognition_results": result.get('recognition_results', [])...}
        # But the raw LogMeal response has 'segmentation_results' at root, usually.
        # Let's verify what `result` is in _process_base64_image. 
        # It calls result = response.json(). 
        # If response has 'segmentation_results', we should pass that potentially.
        # I will patch _process_base64_image to include raw response or verify where segmentation_results are.
        # Based on user payload: root has "segmentation_results". "recognition_results" is NOT at root.
        # So `result.get('recognition_results', [])` in `_process_base64_image` will be EMPTY!
        # logic error in _process_base64_image needs fixing first or concurrent with this.
        
        # ACTUALLY, I must fix _process_base64_image to return the 'segmentation_results' correctly.
        # I will assume I fix that in this same replacement block or separate.
        # Since I can replace lines 207-287, I can't reach line 100 easily without a huge block.
        # I will use multi_replace to handle both if needed, OR just handle the logic here 
        # assuming I fix the other method next. 
        # But `recognize_food_from_base64` calls `_process_base64_image`.
        # If `_process_base64_image` drops the data, I can't recover it here.
        # I MUST fix `_process_base64_image` first or using AllowMultiple?
        # I'll do a separate tool call to fix `_process_base64_image` to return the full raw result,
        # verifying the flow.
        pass # Placeholder for thought process.
        
        # Since I'm in the middle of generating the replacement, I will assume 
        # I will Fix `_process_base64_image` in the NEXT step.
        # For this function, I will write code that EXPECTS `recognition_response` to contain the raw data
        # or properly mapped data.
        
        # Let's write this function assuming `recognition_response` WILL contain 'segmentation_results'.
        
        segmentation_results = recognition_response.get("segmentation_results", [])
        if not segmentation_results:
             # Fallback if mapped to recognition_results
             segmentation_results = recognition_response.get("recognition_results", [])

        # Find best match
        best_item = self._extract_top_food_item(segmentation_results)
        
        if not best_item:
            return {
                "success": True,
                "recognized_dish": None,
                "message": "No specific food items recognized with sufficient confidence"
            }
        
        # Get ingredients for this specific dish
        ingredients_result = {}
        if 'id' in best_item:
            ingredients_result = self.get_recipe_ingredients(best_item['id'])
        
        return {
            "success": True,
            "recognized_dish": {
                "name": best_item.get('name'),
                "id": best_item.get('id'),
                "confidence": best_item.get('prob'),
                "food_family": best_item.get('foodFamily', [])
            },
            "ingredients_info": ingredients_result.get("ingredients", {}) if ingredients_result.get("success") else {},
            "image_analysis_id": recognition_response.get("image_analysis_id")
        }