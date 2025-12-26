#!/usr/bin/env python3
"""
Nutrition analysis tools using LogMeal API with local image storage.
"""

import os
import logging
from typing import Dict, Any, List
from fastmcp import FastMCP
from logmeal_client import LogMealClient
from config import settings
import tempfile
import requests
from urllib.parse import urlparse
import base64
import io
from PIL import Image
import re
import uuid
from pathlib import Path

logger = logging.getLogger("mcp_recipe_server.nutrition")

# Initialize LogMeal client
logmeal_client = LogMealClient(
    api_key=settings.LOGMEAL_API_KEY,
    base_url=settings.LOGMEAL_API_URL
)

# Define image storage directory at module level
PROJECT_ROOT = Path(__file__).parent.parent
IMAGE_STORAGE_DIR = PROJECT_ROOT / "resources" / "images"
IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

logger.info(f"Image storage directory: {IMAGE_STORAGE_DIR}")


# --- Helper Functions (Module Level) ---

def _is_valid_url(url: str) -> bool:
    """Check if the string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def _is_data_url(url: str) -> bool:
    """Check if the string is a data URL (base64 encoded image)."""
    return url.startswith('data:image/')

def _extract_base64_from_data_url(data_url: str) -> str:
    """Extract base64 data from a data URL."""
    match = re.search(r'base64,(.*)', data_url)
    if match:
        return match.group(1)
    return data_url

def _save_image_to_storage(image_bytes: bytes, filename: str = None) -> Dict[str, Any]:
    """Save image bytes to the resources/images folder."""
    try:
        # Generate filename if not provided
        if not filename:
            filename = f"image_{uuid.uuid4().hex[:8]}.jpg"
        
        file_path = IMAGE_STORAGE_DIR / filename
        
        # Save image
        with open(file_path, "wb") as f:
            f.write(image_bytes)
        
        file_size = os.path.getsize(file_path)
        logger.info(f"Saved image to: {file_path} ({file_size} bytes)")
        
        return {
            "success": True,
            "file_path": str(file_path),
            "filename": filename,
            "file_size": file_size,
            "storage_dir": str(IMAGE_STORAGE_DIR)
        }
        
    except Exception as e:
        logger.error(f"Failed to save image to storage: {e}")
        return {
            "success": False,
            "error": f"Failed to save image: {str(e)}"
        }

def _get_image_from_storage(filename: str) -> Dict[str, Any]:
    """Get image from storage by filename."""
    try:
        file_path = IMAGE_STORAGE_DIR / filename
        
        if not file_path.exists():
            return {
                "success": False,
                "error": f"Image not found: {filename}",
                "storage_dir": str(IMAGE_STORAGE_DIR)
            }
        
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        
        return {
            "success": True,
            "image_bytes": image_bytes,
            "file_path": str(file_path),
            "file_size": len(image_bytes),
            "filename": filename
        }
        
    except Exception as e:
        logger.error(f"Failed to get image from storage: {e}")
        return {
            "success": False,
            "error": f"Failed to get image: {str(e)}"
        }

def _list_stored_images() -> Dict[str, Any]:
    """List all images in the storage directory."""
    try:
        images = []
        for file_path in IMAGE_STORAGE_DIR.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                images.append({
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "file_size": os.path.getsize(file_path),
                    "modified": os.path.getmtime(file_path)
                })
        
        return {
            "success": True,
            "images": images,
            "count": len(images),
            "storage_dir": str(IMAGE_STORAGE_DIR)
        }
        
    except Exception as e:
        logger.error(f"Failed to list stored images: {e}")
        return {
            "success": False,
            "error": f"Failed to list images: {str(e)}"
        }

def _process_image_data_to_storage(image_data: str, filename: str = None) -> Dict[str, Any]:
    """Process image data and save to storage."""
    try:
        image_bytes = None
        
        # Check if it's a data URL
        if _is_data_url(image_data):
            logger.info("Processing data URL")
            # Extract base64 from data URL
            base64_data = _extract_base64_from_data_url(image_data)
            # Decode base64 to bytes
            image_bytes = base64.b64decode(base64_data)
            
        # Check if it's a regular URL
        elif _is_valid_url(image_data):
            # Check for private GitHub user content that we can't access
            if "github.com/user-attachments" in image_data:
                return {
                    "success": False,
                    "error": (
                        "Cannot access private GitHub attachment URLs directly. "
                        "Please ask the user to provide the local file path of the image "
                        "or try to extract the base64 data from the chat context."
                    )
                }

            logger.info(f"Downloading image from URL: {image_data}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(image_data, headers=headers, timeout=30)
            
            # Handle 404/403 specifically for better error messages
            if response.status_code in [403, 404] and "github" in image_data:
                 return {
                    "success": False,
                    "error": (
                        f"Failed to download image (Status {response.status_code}). "
                        "This looks like a private GitHub URL which the server cannot access. "
                        "Please use a public URL, local file path, or base64 data."
                    )
                }
            
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                return {
                    "success": False,
                    "error": f"URL does not point to an image. Content-Type: {content_type}"
                }
            
            image_bytes = response.content
            
        else:
            # Assume it's already base64 encoded (without data URL prefix)
            logger.info("Processing base64 string")
            try:
                image_bytes = base64.b64decode(image_data)
            except:
                return {
                    "success": False,
                    "error": "Invalid image input. Must be URL, data URL, or base64 string"
                }
        
        # Save to storage
        return _save_image_to_storage(image_bytes, filename)
        
    except Exception as e:
        logger.error(f"Failed to process image data: {e}")
        return {
            "success": False,
            "error": f"Failed to process image: {str(e)}"
        }

# --- Core Logic Functions (Async) ---

async def analyze_saved_image_impl(filename: str) -> Dict[str, Any]:
    """Analyze food image from the resources/images folder."""
    # Get image from storage
    image_data = _get_image_from_storage(filename)
    if not image_data["success"]:
        return image_data
    
    try:
        logger.info(f"Analyzing saved image: {filename}")
        
        # Convert bytes to base64 for LogMeal API
        image_bytes = image_data["image_bytes"]
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Analyze using LogMeal
        result = logmeal_client.analyze_food_from_base64(image_base64)
        
        if result["success"]:
            result["image_info"] = {
                "filename": filename,
                "file_path": image_data["file_path"],
                "file_size": image_data["file_size"],
                "storage_dir": str(IMAGE_STORAGE_DIR)
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Food image analysis failed: {e}")
        return {
            "success": False,
            "error": f"Analysis failed: {str(e)}",
            "filename": filename
        }

async def analyze_food_image_url_impl(image_url: str) -> Dict[str, Any]:
    """Analyze food image from a URL or data URL."""
    if not image_url:
        return {
            "success": False,
            "error": "Image URL or data is required"
        }
    
    # Save image to storage first
    save_result = _process_image_data_to_storage(image_url)
    if not save_result["success"]:
        return save_result
    
    filename = save_result["filename"]
    
    # Analyze the saved image
    return await analyze_saved_image_impl(filename)

async def analyze_food_image_path_impl(image_path: str) -> Dict[str, Any]:
    """Analyze food image from a file path."""
    try:
        logger.info(f"Analyzing food image from file: {image_path}")
        result = logmeal_client.analyze_food_image(image_path)
        
        if result["success"]:
            result["path_info"] = {
                "file_path": image_path,
                "file_size": os.path.getsize(image_path) if os.path.exists(image_path) else 0
            }
        
        return result
        
    except Exception as e:
        logger.error(f"Food image analysis failed: {e}")
        return {
            "success": False,
            "error": f"Analysis failed: {str(e)}",
            "file_path": image_path
        }

async def analyze_food_image_impl(image_input: str) -> Dict[str, Any]:
    """Universal food image analyzer."""
    # First check if it's a filename in storage
    stored_images = _list_stored_images()
    if stored_images["success"]:
        for image in stored_images["images"]:
            if image["filename"] == image_input:
                logger.info(f"Detected stored image filename: {image_input}")
                return await analyze_saved_image_impl(image_input)
    
    # Check if it's a URL or data URL
    if _is_data_url(image_input) or _is_valid_url(image_input):
        logger.info(f"Detected URL/data URL input")
        return await analyze_food_image_url_impl(image_input)
    else:
        # Check if it's a base64 string
        try:
            # Try to decode as base64 (preview check)
            base64.b64decode(image_input[:100] + "==")
            logger.info("Detected base64 string input")
            return await analyze_food_image_url_impl(image_input)
        except:
            # Assume it's a file path
            logger.info(f"Detected file path input: {image_input}")
            return await analyze_food_image_path_impl(image_input)


# --- MCP Tool Registration ---

def init_nutrition_tools(mcp: FastMCP):
    """Initialize all nutrition-related tools."""
    
    @mcp.tool()
    async def save_image_from_url(image_url: str, filename: str = None) -> Dict[str, Any]:
        """
        Save image from URL or data URL to resources/images folder.
        """
        return _process_image_data_to_storage(image_url, filename)

    @mcp.tool()
    async def save_image_from_bytes(image_bytes: bytes, filename: str = None) -> Dict[str, Any]:
        """
        Save raw image bytes to resources/images folder.
        """
        return _save_image_to_storage(image_bytes, filename)

    @mcp.tool()
    async def list_saved_images() -> Dict[str, Any]:
        """
        List all images saved in the resources/images folder.
        """
        return _list_stored_images()

    @mcp.tool()
    async def analyze_saved_image(filename: str) -> Dict[str, Any]:
        """
        Analyze food image from the resources/images folder.
        """
        return await analyze_saved_image_impl(filename)

    @mcp.tool()
    async def analyze_food_image_url(image_url: str) -> Dict[str, Any]:
        """
        Analyze food image from a URL or data URL.
        Automatically saves to storage first.
        """
        return await analyze_food_image_url_impl(image_url)
    
    @mcp.tool()
    async def analyze_food_image(image_input: str) -> Dict[str, Any]:
        """
        Universal food image analyzer that accepts:
        - Direct image URLs (http/https)
        - Data URLs (base64 encoded images)
        - Base64 strings
        - File paths
        - Filenames from resources/images folder
        """
        return await analyze_food_image_impl(image_input)
    
    @mcp.tool()
    async def analyze_food_image_path(image_path: str) -> Dict[str, Any]:
        """
        Legacy function for file path analysis.
        Kept for backward compatibility.
        """
        return await analyze_food_image_path_impl(image_path)

    @mcp.tool()
    async def analyze_claude_upload(image_bytes: bytes) -> Dict[str, Any]:
        """
        Special handler for Claude Desktop image uploads.
        Saves to resources/images folder and analyzes.
        """
        # Save to storage
        save_result = _save_image_to_storage(image_bytes)
        if not save_result["success"]:
            return save_result
        
        filename = save_result["filename"]
        
        # Analyze
        return await analyze_saved_image_impl(filename)

    @mcp.tool()
    async def delete_saved_image(filename: str) -> Dict[str, Any]:
        """
        Delete an image from the resources/images folder.
        """
        try:
            file_path = IMAGE_STORAGE_DIR / filename
            
            if not file_path.exists():
                return {
                    "success": False,
                    "error": f"Image not found: {filename}"
                }
            
            file_size = os.path.getsize(file_path)
            os.remove(file_path)
            
            logger.info(f"Deleted image: {filename}")
            
            return {
                "success": True,
                "message": f"Deleted {filename} ({file_size} bytes)",
                "filename": filename,
                "file_size": file_size
            }
            
        except Exception as e:
            logger.error(f"Failed to delete image: {e}")
            return {
                "success": False,
                "error": f"Failed to delete image: {str(e)}"
            }

    @mcp.tool()
    async def clear_image_storage() -> Dict[str, Any]:
        """
        Clear all images from the resources/images folder.
        """
        try:
            deleted_count = 0
            total_size = 0
            
            for file_path in IMAGE_STORAGE_DIR.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_count += 1
                    total_size += file_size
            
            logger.info(f"Cleared storage: {deleted_count} images deleted")
            
            return {
                "success": True,
                "message": f"Deleted {deleted_count} images ({total_size} bytes total)",
                "deleted_count": deleted_count,
                "total_size": total_size
            }
            
        except Exception as e:
            logger.error(f"Failed to clear storage: {e}")
            return {
                "success": False,
                "error": f"Failed to clear storage: {str(e)}"
            }

    @mcp.tool()
    async def get_image_storage_info() -> Dict[str, Any]:
        """
        Get information about the image storage directory.
        """
        try:
            images = _list_stored_images()
            
            if not images["success"]:
                return images
            
            total_size = sum(img["file_size"] for img in images["images"])
            
            return {
                "success": True,
                "storage_dir": str(IMAGE_STORAGE_DIR),
                "image_count": images["count"],
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "exists": IMAGE_STORAGE_DIR.exists(),
                "writable": os.access(IMAGE_STORAGE_DIR, os.W_OK)
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            return {
                "success": False,
                "error": f"Failed to get storage info: {str(e)}"
            }

    @mcp.tool()
    async def get_food_nutrition(food_items: List[str]) -> Dict[str, Any]:
        """
        Get nutrition information for specific food items.
        """
        if not food_items:
            return {
                "success": False,
                "error": "At least one food item is required"
            }
        
        try:
            logger.info(f"Getting nutrition for {len(food_items)} food items")
            result = logmeal_client.get_nutrition_info(food_items)
            return result
            
        except Exception as e:
            logger.error(f"Nutrition analysis failed: {e}")
            return {
                "success": False,
                "error": f"Nutrition analysis failed: {str(e)}"
            }

    @mcp.tool()
    async def estimate_recipe_nutrition(ingredients: List[str], servings: int = 1) -> Dict[str, Any]:
        """
        Estimate nutrition information for a recipe based on ingredients.
        """
        if not ingredients:
            return {
                "success": False,
                "error": "At least one ingredient is required"
            }
        
        try:
            logger.info(f"Estimating nutrition for recipe with {len(ingredients)} ingredients")
            
            # Get nutrition for main ingredients (limit to avoid API overload)
            main_ingredients = ingredients[:10]  # Limit to first 10 ingredients
            nutrition_result = logmeal_client.get_nutrition_info(main_ingredients)
            
            if not nutrition_result["success"]:
                return nutrition_result
            
            # Process and summarize nutrition info
            nutrition_info = nutrition_result.get("nutrition_info", {})
            
            return {
                "success": True,
                "ingredients_analyzed": main_ingredients,
                "total_ingredients": len(ingredients),
                "servings": servings,
                "nutrition_summary": nutrition_info,
                "note": f"Analyzed {len(main_ingredients)} of {len(ingredients)} ingredients"
            }
            
        except Exception as e:
            logger.error(f"Recipe nutrition estimation failed: {e}")
            return {
                "success": False,
                "error": f"Nutrition estimation failed: {str(e)}"
            }

    # MCP Resource to serve stored images
    @mcp.resource("image://{filename}")
    async def get_stored_image(filename: str) -> bytes:
        """
        MCP Resource to serve stored images as binary data.
        """
        image_data = _get_image_from_storage(filename)
        if image_data["success"]:
            return image_data["image_bytes"]
        else:
            raise ValueError(f"Image not found: {filename}")

    # MCP Resource to list stored images
    @mcp.resource("images://list")
    async def list_images_resource() -> str:
        """
        MCP Resource to list all stored images.
        """
        import json
        result = _list_stored_images()
        return json.dumps(result, indent=2)