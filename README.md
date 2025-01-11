# Weather Information App

A comprehensive Flask-based weather application that provides current weather data, forecasts, and location-based information, including YouTube videos and Wikipedia articles.

## Features

### Weather Information
- Current weather conditions
- 5-day weather forecast
- Historical weather data
- Save weather records for different locations

### Location Features
- Support for city names, ZIP codes, and coordinates
- Interactive map integration
- Geolocation support
- Location suggestions and autocomplete

### Additional Information
- YouTube travel guides for locations
- Wikipedia information about locations
- Interactive maps showing selected locations

### Data Management
- Save and manage weather records
- Export data in multiple formats (CSV, PDF)
- Update and delete saved records

## Prerequisites

- Python 3.7 or higher
- API Keys for:
  - OpenWeatherMap API
  - YouTube Data API
  - Google Maps API

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd weather-app
   ```

2. **Install required packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** in the root directory with your API keys or edit within app.py and indexl.html:
   ```env
   OPENWEATHER_API_KEY=your_openweather_api_key
   YOUTUBE_API_KEY=your_youtube_api_key
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key
   ```

4. **Update the API keys** in `app.py` and `index.html`:
   - Replace `YOUR_OPEN_WEATHER_API` in `app.py`.
   - Replace `YOUR_API` for YouTube API in `app.py`.
   - Update the Google Maps API key in the `<script>` tag in `index.html`.

## Running the Application

1. **Initialize the database:**
   ```bash
   python
   >>> from app import app, db
   >>> with app.app_context():
   ...     db.create_all()
   >>> exit()
   ```

2. **Start the Flask application:**
   ```bash
   python app.py
   ```

3. **Open a web browser** and navigate to:
   ```
   http://localhost:5000
   ```

## Usage

1. **Search for a Location:**
   - Enter a city name, ZIP code, or coordinates.
   - Select from the suggested locations.

2. **View Weather Information:**
   - Click "Get Weather" for current conditions.
   - Click "Get Forecast" for a 5-day forecast.
   - Use "Use Your Location" for local weather.

3. **Save Weather Records:**
   - Select dates and a location.
   - Click "Save Weather Record."
   - View saved records in the bottom panel.

4. **Export Data:**
   - Use the export dropdown to save data in CSV or PDF format.

## Database

The application uses SQLite for data storage. The database file (`weather.db`) will be created automatically in the project directory when you first run the application.

## Error Handling

The application includes error handling for:
- Invalid locations
- API failures
- Database errors
- Export errors

## License

[MIT License](LICENSE)