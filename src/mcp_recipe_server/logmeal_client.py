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
            payload = {
                "image": image_base64
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            result = response.json()
            return {
                "success": True,
                "recognition_results": result.get('recognition_results', []),
                "image_analysis_id": result.get('image_analysis_id')
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

    def get_nutrition_info(self, food_items: List[str]) -> Dict[str, Any]:
        """
        Get nutrition information for food items.
        
        Args:
            food_items: List of food item names
            
        Returns:
            Nutrition information
        """
        try:
            logger.info(f"Getting nutrition info for {len(food_items)} items: {food_items}")
            
            url = f"{self.base_url}/nutrition"
            payload = {
                "food_items": food_items
            }
            
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            
            result = response.json()
            logger.info("Nutrition analysis successful")
            
            return {
                "success": True,
                "nutrition_info": result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Nutrition API request failed: {e}")
            return {
                "success": False,
                "error": f"Nutrition analysis failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Nutrition analysis failed: {e}")
            return {
                "success": False,
                "error": f"Nutrition analysis failed: {str(e)}"
            }

    def analyze_food_image(self, image_path: str) -> Dict[str, Any]:
        """
        Complete analysis: recognize food and get nutrition info from file path.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Complete analysis results
        """
        # First recognize food items
        recognition_result = self.recognize_food(image_path)
        if not recognition_result["success"]:
            return recognition_result
        
        # Extract food names
        food_items = []
        for item in recognition_result.get("recognition_results", []):
            food_name = item.get("name")
            if food_name:
                food_items.append(food_name)
        
        if not food_items:
            return {
                "success": True,
                "recognized_foods": [],
                "nutrition_info": {},
                "message": "No specific food items recognized"
            }
        
        # Get nutrition information
        nutrition_result = self.get_nutrition_info(food_items)
        
        return {
            "success": True,
            "recognized_foods": food_items,
            "recognition_details": recognition_result.get("recognition_results", []),
            "nutrition_info": nutrition_result.get("nutrition_info", {}) if nutrition_result["success"] else {},
            "image_analysis_id": recognition_result.get("image_analysis_id")
        }

    def analyze_food_from_base64(self, image_base64: str) -> Dict[str, Any]:
        """
        Complete analysis: recognize food and get nutrition info from base64.
        
        Args:
            image_base64: Base64 encoded image string
            
        Returns:
            Complete analysis results
        """
        # First recognize food items
        recognition_result = self.recognize_food_from_base64(image_base64)
        if not recognition_result["success"]:
            return recognition_result
        
        # Extract food names
        food_items = []
        for item in recognition_result.get("recognition_results", []):
            food_name = item.get("name")
            if food_name:
                food_items.append(food_name)
        
        if not food_items:
            return {
                "success": True,
                "recognized_foods": [],
                "nutrition_info": {},
                "message": "No specific food items recognized"
            }
        
        # Get nutrition information
        nutrition_result = self.get_nutrition_info(food_items)
        
        return {
            "success": True,
            "recognized_foods": food_items,
            "recognition_details": recognition_result.get("recognition_results", []),
            "nutrition_info": nutrition_result.get("nutrition_info", {}) if nutrition_result["success"] else {},
            "image_analysis_id": recognition_result.get("image_analysis_id")
        }