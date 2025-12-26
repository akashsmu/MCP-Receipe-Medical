#!/usr/bin/env python3
"""
Main MCP Server integrating Recipe Generation and Food Analysis tools.
"""

import sys
import os
import logging
from typing import Any, Dict
from fastmcp import FastMCP

# Add the parent directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(parent_dir)
sys.path.insert(0, project_root)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("mcp_recipe_server")

# Load environment variables
from dotenv import load_dotenv
env_path = os.path.join(project_root, '.env')
logger.info(f"Loading environment from: {env_path}")
load_dotenv(env_path)

# Import after path setup
from config import settings

# Import tool modules
try:
    from recipe_tools import init_recipe_tools, generate_recipe_impl
    logger.info("✅ Successfully imported recipe_tools")
except ImportError as e:
    logger.error(f"Failed to import recipe_tools: {e}")
    def init_recipe_tools(mcp):
        logger.warning("Using dummy recipe_tools due to import error")
    
    async def generate_recipe_impl(*args, **kwargs):
        return {"success": False, "error": "Recipe tools not available"}

# Initialize main MCP server
mcp = FastMCP("Enhanced Recipe Server", instructions="""
CRITICAL SYSTEM INSTRUCTIONS FOR IMAGE HANDLING:

1. IMAGE UPLOADS FROM CHAT:
   - ⚠️ DO NOT use the URL if it is a private link (e.g., `github.com/user-attachments`). The server CANNOT access these.
   - instead, ask the user for the **local file path** of the image.
   - OR, if you can extract the image as base64, pass that to `analyze_food_image`.

2. STORAGE-BASED WORKFLOW:
   - For public URLs: Use `analyze_food_image_url`
   - For file paths: Use `analyze_food_image`
   
3. IMAGE MANAGEMENT:
   - List saved images: `list_saved_images`
   - All images are saved to: resources/images/
""")

def integrate_all_tools():
    """Integrate all tools from different modules."""
    logger.info("🔄 Integrating tools from all modules...")
    
    # Initialize recipe tools
    try:
        init_recipe_tools(mcp)
        logger.info("✅ Recipe tools initialized")
    except Exception as e:
        logger.error(f"Failed to initialize recipe tools: {e}")
        
        @mcp.tool()
        async def generate_recipe(
            ingredients: list,
            cuisine: str = "any",
            dietary_preference: str = "none",
            style: str = "detailed"
        ) -> dict:
            return {
                "success": False,
                "error": "Recipe tools not available",
                "fallback_message": "Recipe generation service is temporarily unavailable."
            }
    
    # Initialize nutrition tools
    try:
        # Import nutrition_tools
        from nutrition_tools import init_nutrition_tools, analyze_food_image_impl
        # Call init_nutrition_tools to register all tools
        init_nutrition_tools(mcp)
        logger.info("✅ Nutrition tools initialized via init_nutrition_tools")
        
    except ImportError as e:
        logger.error(f"Failed to import nutrition_tools: {e}")
        
        @mcp.tool()
        async def analyze_food_image_url(image_url: str) -> Dict[str, Any]:
            return {
                "success": False,
                "error": "Nutrition tools not available",
                "help": "Make sure nutrition_tools.py exists and is properly configured"
            }
        
        # Define dummy impl for local usage if import fails
        async def analyze_food_image_impl(image_input):
            return {"success": False, "error": "Nutrition tools not available"}
    
    # Define combined tool that uses the imported implementation directly
    @mcp.tool()
    async def analyze_and_suggest_recipe(image_input: str, cuisine: str = "any") -> Dict[str, Any]:
        """
        Combined tool that uses both nutrition and recipe tools.
        """
        try:
            # Use the implementation function directly, bypassing the tool wrapper issues
            analysis_result = await analyze_food_image_impl(image_input)
            
            if not analysis_result.get("success", False):
                return analysis_result
            
            recognized_foods = analysis_result.get("recognized_foods", [])
            
            if not recognized_foods:
                return {
                    "success": True,
                    "message": "No specific food items recognized in the image",
                    "analysis": analysis_result,
                    "recipe_suggestions": []
                }
            
            # Generate recipe based on recognized foods using the implementation function
            recipe_result = await generate_recipe_impl(
                ingredients=recognized_foods,
                cuisine=cuisine,
                dietary_preference="none",
                style="detailed"
            )
            
            return {
                "success": True,
                "recognized_foods": recognized_foods,
                "nutrition_info": analysis_result.get("nutrition_info", {}),
                "recipe_suggestions": [recipe_result] if recipe_result.get("success") else [],
                "analysis_id": analysis_result.get("image_analysis_id")
            }
            
        except Exception as e:
            logger.error(f"Failed in analyze_and_suggest_recipe: {e}")
            return {
                "success": False,
                "error": f"Combined analysis failed: {str(e)}",
                "input_received": image_input
            }

    @mcp.resource("config://server")
    async def get_enhanced_server_config():
        """Get server configuration."""
        capabilities = {
            "recipe_generation": True,
            "food_recognition": True,
            "nutrition_analysis": True,
            "image_analysis": True,
            "inline_image_support": True,
            "url_image_support": True,
            "image_storage": True
        }
        
        return {
            "name": "Enhanced Recipe Server",
            "version": "1.0.0",
            "capabilities": capabilities,
            "supported_cuisines": [
                "any", "italian", "mexican", "chinese", "indian", 
                "french", "thai", "japanese", "american", "mediterranean"
            ],
            "supported_diets": [
                "none", "vegetarian", "vegan", "gluten_free", 
                "dairy_free", "keto", "paleo"
            ]
        }
    
    logger.info("✅ All tools integrated successfully")

def main():
    """Run the MCP server."""
    try:
        # Validate configuration
        logger.info("🔧 Validating configuration...")
        try:
            settings.validate()
            logger.info("✅ Configuration validated successfully")
            logger.info(f"Using OpenAI model: {settings.OPENAI_MODEL}")
            logger.info(f"LogMeal API configured: {'Yes' if settings.LOGMEAL_API_KEY else 'No'}")
        except Exception as e:
            logger.warning(f"⚠️  Configuration validation failed: {e}")
            logger.info("Continuing with default settings...")
        
        integrate_all_tools()
        
        logger.info("🚀 Starting Enhanced Recipe Server")
        logger.info("🔧 Server initialization complete")
        
        mcp.run(transport="stdio")
        
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()