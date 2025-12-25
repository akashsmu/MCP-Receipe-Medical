#!/usr/bin/env python3
"""
Recipe tools module - exports initialization function.
"""

import asyncio
import sys
import os
from typing import List, Optional, Dict, Any
import logging

# Add the parent directory to Python path so we can import from config
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

# Load environment variables BEFORE any imports that need them
from dotenv import load_dotenv
# Load .env from the project root (one level up from src)
env_path = os.path.join(project_root, '.env')
logger.info(f"Loading environment from: {env_path}")
load_dotenv(env_path)

# Now import after adding to path and loading environment
from fastmcp import FastMCP
from openai import AsyncOpenAI

# Import settings: prefer package-relative import (when run with -m),
# but fall back to a plain import when the module is run directly as a script.
try:
    from .config import settings
except ImportError:
    # Direct script execution usually makes src/mcp_recipe_server the cwd entry on sys.path,
    # so `import config` will resolve to src/mcp_recipe_server/config.py.
    try:
        from config import settings
    except ImportError as e:
        logger.error(f"Failed to import config: {e}")
        # Create a simple settings class as fallback
        class SimpleSettings:
            OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
            OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
            SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
            SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
            
            @classmethod
            def validate(cls):
                if not cls.OPENAI_API_KEY:
                    raise ValueError("OPENAI_API_KEY environment variable is required")
                if not cls.OPENAI_API_KEY.startswith("sk-"):
                    raise ValueError("OPENAI_API_KEY appears to be invalid")
        
        settings = SimpleSettings()

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# --- Implementation Functions (Module Level) ---

async def generate_recipe_impl(
    ingredients: List[str],
    cuisine: str = "any",
    dietary_preference: str = "none",
    style: str = "detailed",
    cooking_time: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate a recipe based on available ingredients and preferences.
    """
    # Validate inputs
    if not ingredients:
        return {
            "success": False,
            "error": "At least one ingredient is required"
        }
    
    if len(ingredients) > 20:
        return {
            "success": False, 
            "error": "Too many ingredients (maximum 20)"
        }

    # Build the prompt
    cooking_time_text = f" within {cooking_time} minutes" if cooking_time else ""
    dietary_text = f" that is {dietary_preference}" if dietary_preference != "none" else ""
    
    prompt = f"""
    Create a {style} recipe {dietary_text} in {cuisine} style{cooking_time_text} 
    using these ingredients: {', '.join(ingredients)}.
    
    Return the recipe as a structured response with:
    - A creative title
    - List of all ingredients needed (you can add common pantry items)
    - Clear, step-by-step cooking instructions
    - Estimated cooking time
    - Difficulty level
    - Number of servings
    - Any helpful tips or variations
    """
    
    try:
        logger.info(f"Generating recipe for {len(ingredients)} ingredients, cuisine: {cuisine}")
        
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional chef. Create practical, delicious recipes."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        recipe_content = response.choices[0].message.content
        logger.info(f"Successfully generated recipe for ingredients: {ingredients}")
        
        return {
            "success": True,
            "recipe": recipe_content,
            "ingredients_used": ingredients,
            "cuisine": cuisine,
            "dietary_preference": dietary_preference
        }
        
    except Exception as e:
        logger.error(f"Failed to generate recipe: {e}")
        return {
            "success": False,
            "error": f"Failed to generate recipe: {str(e)}",
            "ingredients": ingredients
        }

async def suggest_ingredient_substitutions_impl(
    ingredient: str, 
    reason: str = "allergy",
    flavor_profile: str = "similar taste"
) -> Dict[str, Any]:
    """
    Suggest substitutions for a specific ingredient.
    """
    if not ingredient.strip():
        return {
            "success": False,
            "error": "Ingredient cannot be empty"
        }
    
    prompt = f"""
    Suggest 3-5 good substitutions for {ingredient} for {reason} of {flavor_profile}.
    For each substitution, provide:
    - The substitute ingredient
    - Why it's a good substitute
    - Any adjustments needed in quantity or preparation
    
    Format the response as a clear, bulleted list.
    """
    
    try:
        logger.info(f"Generating substitutions for {ingredient} (reason: {reason})")
        
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800
        )
        
        content = response.choices[0].message.content
        # Simple parsing - split by lines and filter empty ones
        substitutions = [line.strip() for line in content.split('\n') if line.strip()]
        
        logger.info(f"Generated {len(substitutions)} substitutions for {ingredient}")
        
        return {
            "success": True,
            "ingredient": ingredient,
            "reason": reason,
            "flavor_profile": flavor_profile,
            "substitutions": substitutions
        }
        
    except Exception as e:
        logger.error(f"Failed to generate substitutions: {e}")
        return {
            "success": False,
            "ingredient": ingredient,
            "error": f"Failed to generate substitutions: {str(e)}"
        }

# --- Tool Initialization ---

def init_recipe_tools(mcp_instance: FastMCP):
    """Initialize all recipe tools with the provided MCP instance."""
    
    @mcp_instance.tool()
    async def generate_recipe(
        ingredients: List[str],
        cuisine: str = "any",
        dietary_preference: str = "none",
        style: str = "detailed",
        cooking_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Generate a recipe based on available ingredients and preferences.
        """
        return await generate_recipe_impl(
            ingredients=ingredients,
            cuisine=cuisine,
            dietary_preference=dietary_preference,
            style=style,
            cooking_time=cooking_time
        )

    @mcp_instance.tool()
    async def suggest_ingredient_substitutions(
        ingredient: str, 
        reason: str = "allergy",
        flavor_profile: str = "similar taste"
    ) -> Dict[str, Any]:
        """
        Suggest substitutions for a specific ingredient.
        """
        return await suggest_ingredient_substitutions_impl(
            ingredient=ingredient,
            reason=reason,
            flavor_profile=flavor_profile
        )

    logger.info("✅ Recipe tools initialized successfully")

# Export the functions for internal use
__all__ = [
    "init_recipe_tools",
    "generate_recipe_impl", 
    "suggest_ingredient_substitutions_impl"
]