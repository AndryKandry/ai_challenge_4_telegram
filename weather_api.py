#!/usr/bin/env python3
"""
Simple HTTP API wrapper for Weather functionality.
Provides a reliable alternative to MCP SDK which has bugs with stdio/SSE transports.
"""

from typing import Any
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

app = FastAPI(title="Weather API", version="1.0.0")


# Request models
class AlertRequest(BaseModel):
    state: str


class ForecastRequest(BaseModel):
    latitude: float
    longitude: float


# Helper functions
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error making NWS request: {e}")
            return None


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""


# API endpoints
@app.get("/")
async def root():
    """Root endpoint - API info."""
    return {
        "name": "Weather API",
        "version": "1.0.0",
        "tools": [
            {
                "name": "get_alerts",
                "description": "Get weather alerts for a US state",
                "endpoint": "/tools/get_alerts",
                "method": "POST",
                "parameters": {"state": "Two-letter US state code (e.g. CA, NY)"}
            },
            {
                "name": "get_forecast",
                "description": "Get weather forecast for a location",
                "endpoint": "/tools/get_forecast",
                "method": "POST",
                "parameters": {
                    "latitude": "Latitude of the location",
                    "longitude": "Longitude of the location"
                }
            }
        ]
    }


@app.get("/tools")
async def list_tools():
    """List available tools in MCP-compatible format."""
    return {
        "tools": [
            {
                "name": "get_alerts",
                "description": "Get weather alerts for a US state",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "description": "Two-letter US state code (e.g. CA, NY)"
                        }
                    },
                    "required": ["state"]
                }
            },
            {
                "name": "get_forecast",
                "description": "Get weather forecast for a location",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "latitude": {
                            "type": "number",
                            "description": "Latitude of the location"
                        },
                        "longitude": {
                            "type": "number",
                            "description": "Longitude of the location"
                        }
                    },
                    "required": ["latitude", "longitude"]
                }
            }
        ]
    }


@app.post("/tools/get_alerts")
async def get_alerts(request: AlertRequest):
    """Get weather alerts for a US state."""
    url = f"{NWS_API_BASE}/alerts/active/area/{request.state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        raise HTTPException(status_code=500, detail="Unable to fetch alerts")

    if not data["features"]:
        return {"result": "No active alerts for this state."}

    alerts = [format_alert(feature) for feature in data["features"]]
    return {"result": "\n---\n".join(alerts)}


@app.post("/tools/get_forecast")
async def get_forecast(request: ForecastRequest):
    """Get weather forecast for a location."""
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{request.latitude},{request.longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        raise HTTPException(status_code=500, detail="Unable to fetch forecast data for this location")

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        raise HTTPException(status_code=500, detail="Unable to fetch detailed forecast")

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return {"result": "\n---\n".join(forecasts)}


if __name__ == "__main__":
    print("🌤️  Starting Weather API server...")
    print("📍 Server will be available at: http://127.0.0.1:8000")
    print("📚 API docs: http://127.0.0.1:8000/docs")
    print("🛠️  Tools list: http://127.0.0.1:8000/tools")
    uvicorn.run(app, host="127.0.0.1", port=8000)
