from langchain_core.tools import tool
from typing import Dict, Any
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool
from dotenv import load_dotenv
load_dotenv()
import os
from langchain_tavily import TavilySearch


class WeatherInput(BaseModel):
    city: str = Field(
        description="City name to get weather for. Example: Delhi, London, Tokyo"
    )


search_tool = TavilySearch(
    max_results=5,
    topic="general",          
    search_depth="basic",     
)

os.environ["TAVILY_API_KEY"] 


def get_weather(city: str) -> Dict[str, Any]:
    """
    Get current weather for a city using Open-Meteo.
    """

    geo_url = "https://geocoding-api.open-meteo.com/v1/search"

    geo_response = requests.get(
        geo_url,
        params={
            "name": city,
            "count": 1
        },
        timeout=10
    )

    geo_data = geo_response.json()

    if "results" not in geo_data:
        return {
            "success": False,
            "error": f"City '{city}' not found"
        }

    location = geo_data["results"][0]

    latitude = location["latitude"]
    longitude = location["longitude"]



    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_response = requests.get(
        weather_url,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "wind_speed_10m",
                "weather_code",
                "is_day"
            ]
        },
        timeout=10
    )

    weather_data = weather_response.json()

    current = weather_data["current"]

    return {
        "success": True,
        "city": location["name"],
        "country": location.get("country"),
        "latitude": latitude,
        "longitude": longitude,
        "temperature_c": current["temperature_2m"],
        "feels_like_c": current["apparent_temperature"],
        "humidity": current["relative_humidity_2m"],
        "wind_speed_kmh": current["wind_speed_10m"],
        "weather_code": current["weather_code"],
        "is_day": bool(current["is_day"])
    }


weather_tool = StructuredTool.from_function(
    func=get_weather,
    name="weather_tool",
    description="""
    Get current weather information for a city.

    Input:
    - city: Name of city

    Returns:
    - temperature
    - feels like temperature
    - humidity
    - wind speed
    - weather code
    - coordinates
    """,
    args_schema=WeatherInput,
)

def web_search(q: str):
    """Search the web for current information on a given query."""
    return search_tool.invoke({"query": q})