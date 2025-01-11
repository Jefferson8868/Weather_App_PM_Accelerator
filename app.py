from flask import Flask, request, jsonify, render_template, Response
from io import StringIO
import requests
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json
from googleapiclient.discovery import build
import wikipedia
import csv
from fpdf import FPDF
from googleapiclient.errors import HttpError
import time

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weather.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Weather API configuration
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"
API_KEY = "a372b2f0ecb24304d454efca3dcb95f5"
HISTORICAL_API_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_API_URL = "https://api.openweathermap.org/data/2.5/forecast"
CURRENT_API_URL = "https://api.openweathermap.org/data/2.5/weather"
YOUTUBE_API_KEY="AIzaSyBICO2TDNMEIdLE1ghPo5aaGBvAbX2jUFE"


@app.route('/')
def home():
    return render_template('index.html')


class WeatherRecord(db.Model):
    __tablename__ = 'weather_record'  # explicitly name the table
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    weather_data = db.Column(db.Text, nullable=False)  # Changed from JSON to Text
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def validate_and_get_coordinates(location_input):
    """
    Validate location input and return coordinates using different methods.
    Returns (lat, lon, formatted_location_name) or raises ValueError
    """
    try:
        # Check if input is GPS coordinates (lat,lon)
        if ',' in location_input:
            try:
                lat, lon = map(float, location_input.split(','))
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    # Get location name from coordinates
                    reverse_params = {
                        'lat': lat,
                        'lon': lon,
                        'appid': API_KEY
                    }
                    reverse_response = requests.get(WEATHER_API_URL, params=reverse_params)
                    if reverse_response.status_code == 200:
                        location_name = reverse_response.json().get('name', f"{lat},{lon}")
                        return lat, lon, location_name
            except ValueError:
                pass  # Not valid coordinates, continue to other methods

        # Try direct location name or postal code
        direct_params = {
            'q': location_input,
            'appid': API_KEY,
            'limit': 5  # Get multiple results for fuzzy matching
        }
        response = requests.get("http://api.openweathermap.org/geo/1.0/direct", params=direct_params)
        
        if response.status_code == 200 and response.json():
            locations = response.json()
            # Return the first (best) match
            best_match = locations[0]
            formatted_name = f"{best_match['name']}"
            if 'state' in best_match:
                formatted_name += f", {best_match['state']}"
            if 'country' in best_match:
                formatted_name += f", {best_match['country']}"
            return best_match['lat'], best_match['lon'], formatted_name

        # Try postal code lookup
        zip_params = {
            'zip': location_input,
            'appid': API_KEY
        }
        zip_response = requests.get("http://api.openweathermap.org/geo/1.0/zip", params=zip_params)
        if zip_response.status_code == 200:
            zip_data = zip_response.json()
            return zip_data['lat'], zip_data['lon'], f"{zip_data.get('name', location_input)}, {zip_data.get('country', '')}"

        raise ValueError("Location not found")
    
    except Exception as e:
        raise ValueError(f"Invalid location: {str(e)}")


@app.route('/weather', methods=['GET'])
def get_weather():
    location = request.args.get('location')
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    query_params = {}
    if lat and lon:
        query_params = {'lat': lat, 'lon': lon, 'appid': API_KEY, 'units': 'metric'}
    elif location:
        query_params = {'q': location, 'appid': API_KEY, 'units': 'metric'}
    else:
        return jsonify({"error": "Location or coordinates (lat, lon) are required."}), 400

    try:
        response = requests.get(WEATHER_API_URL, params=query_params)
        if response.status_code != 200:
            return jsonify({"error": "Unable to fetch weather data. Check the location or coordinates."}), response.status_code

        weather_data = response.json()
        return jsonify({
            "location": weather_data.get('name'),
            "temperature": weather_data['main']['temp'],
            "condition": weather_data['weather'][0]['description'],
            "humidity": weather_data['main']['humidity'],
            "wind_speed": weather_data['wind']['speed']
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/weather/save', methods=['POST'])
def save_weather():
    try:
        data = request.json
        location = data.get('location')
        lat = data.get('lat')
        lon = data.get('lon')
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d')
        
        # Get current date at midnight for comparison
        current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        historical_data = []

        # Process each day in the date range
        current_date_ptr = start_date
        while current_date_ptr <= end_date:
            try:
                if current_date_ptr < current_date:
                    # Historical data (past)
                    timestamp = int(time.mktime(current_date_ptr.timetuple()))
                    response = requests.get(
                        'https://api.openweathermap.org/data/2.5/weather',
                        params={
                            'lat': lat,
                            'lon': lon,
                            'dt': timestamp,
                            'appid': API_KEY,
                            'units': 'metric'
                        }
                    )
                    if response.status_code == 200:
                        weather_data = response.json()
                        historical_data.append({
                            'date': current_date_ptr.strftime('%Y-%m-%d'),
                            'temp': weather_data['main']['temp'],
                            'feels_like': weather_data['main']['feels_like'],
                            'humidity': weather_data['main']['humidity'],
                            'wind_speed': weather_data['wind']['speed'],
                            'description': weather_data['weather'][0]['description'],
                            'icon': weather_data['weather'][0]['icon']
                        })
                
                elif current_date_ptr == current_date:
                    # Current day's data
                    response = requests.get(
                        CURRENT_API_URL,
                        params={
                            'lat': lat,
                            'lon': lon,
                            'appid': API_KEY,
                            'units': 'metric'
                        }
                    )
                    if response.status_code == 200:
                        weather_data = response.json()
                        historical_data.append({
                            'date': current_date_ptr.strftime('%Y-%m-%d'),
                            'temp': weather_data['main']['temp'],
                            'feels_like': weather_data['main']['feels_like'],
                            'humidity': weather_data['main']['humidity'],
                            'wind_speed': weather_data['wind']['speed'],
                            'description': weather_data['weather'][0]['description'],
                            'icon': weather_data['weather'][0]['icon']
                        })
                
                else:
                    # Future data (forecast)
                    forecast_response = requests.get(
                        FORECAST_API_URL,
                        params={
                            'lat': lat,
                            'lon': lon,
                            'appid': API_KEY,
                            'units': 'metric'
                        }
                    )
                    if forecast_response.status_code == 200:
                        forecast_data = forecast_response.json()
                        for item in forecast_data['list']:
                            forecast_date = datetime.strptime(item['dt_txt'].split()[0], '%Y-%m-%d')
                            if forecast_date.date() == current_date_ptr.date():
                                historical_data.append({
                                    'date': current_date_ptr.strftime('%Y-%m-%d'),
                                    'temp': item['main']['temp'],
                                    'feels_like': item['main']['feels_like'],
                                    'humidity': item['main']['humidity'],
                                    'wind_speed': item['wind']['speed'],
                                    'description': item['weather'][0]['description'],
                                    'icon': item['weather'][0]['icon']
                                })
                                break

            except Exception as e:
                print(f"Error processing date {current_date_ptr}: {str(e)}")
                # Continue to next date even if there's an error
                pass

            current_date_ptr += timedelta(days=1)

        # Create weather record with the collected data
        weather_record = WeatherRecord(
            location=location,
            start_date=start_date,
            end_date=end_date,
            weather_data=json.dumps({
                'historical': historical_data
            })
        )

        db.session.add(weather_record)
        db.session.commit()

        return jsonify({'message': 'Weather record saved successfully'})

    except Exception as e:
        print(f"Error in save_weather: {str(e)}")
        return jsonify({'error': str(e)}), 500


def format_weather_data(weather_data):
    if isinstance(weather_data, str):
        weather_data = json.loads(weather_data)
    
    historical = weather_data.get('historical', [])
    return historical  # Return the historical data directly


@app.route('/weather/records', methods=['GET'])
def get_weather_records():
    try:
        records = WeatherRecord.query.all()
        formatted_records = []
        
        for record in records:
            weather_data = json.loads(record.weather_data)
            formatted_records.append({
                'id': record.id,
                'location': record.location,
                'start_date': record.start_date.strftime('%Y-%m-%d'),
                'end_date': record.end_date.strftime('%Y-%m-%d'),
                'historical_data': format_weather_data(weather_data)
            })
        
        return jsonify(formatted_records)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/weather/record/<int:id>', methods=['PUT'])
def update_weather_record(id):
    try:
        record = WeatherRecord.query.get_or_404(id)
        data = request.json
        
        if 'location' in data and 'lat' in data and 'lon' in data:
            lat = data['lat']
            lon = data['lon']
            current_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            historical_data = []

            # Process each day in the date range
            current_date_ptr = record.start_date
            while current_date_ptr <= record.end_date:
                try:
                    if current_date_ptr < current_date:
                        # Historical data (past)
                        timestamp = int(time.mktime(current_date_ptr.timetuple()))
                        response = requests.get(
                            'https://api.openweathermap.org/data/2.5/weather',
                            params={
                                'lat': lat,
                                'lon': lon,
                                'dt': timestamp,
                                'appid': API_KEY,
                                'units': 'metric'
                            }
                        )
                        if response.status_code == 200:
                            weather_data = response.json()
                            historical_data.append({
                                'date': current_date_ptr.strftime('%Y-%m-%d'),
                                'temp': weather_data['main']['temp'],
                                'feels_like': weather_data['main']['feels_like'],
                                'humidity': weather_data['main']['humidity'],
                                'wind_speed': weather_data['wind']['speed'],
                                'description': weather_data['weather'][0]['description'],
                                'icon': weather_data['weather'][0]['icon']
                            })
                    
                    elif current_date_ptr == current_date:
                        # Current day's data
                        response = requests.get(
                            CURRENT_API_URL,
                            params={
                                'lat': lat,
                                'lon': lon,
                                'appid': API_KEY,
                                'units': 'metric'
                            }
                        )
                        if response.status_code == 200:
                            weather_data = response.json()
                            historical_data.append({
                                'date': current_date_ptr.strftime('%Y-%m-%d'),
                                'temp': weather_data['main']['temp'],
                                'feels_like': weather_data['main']['feels_like'],
                                'humidity': weather_data['main']['humidity'],
                                'wind_speed': weather_data['wind']['speed'],
                                'description': weather_data['weather'][0]['description'],
                                'icon': weather_data['weather'][0]['icon']
                            })
                    
                    else:
                        # Future data (forecast)
                        forecast_response = requests.get(
                            FORECAST_API_URL,
                            params={
                                'lat': lat,
                                'lon': lon,
                                'appid': API_KEY,
                                'units': 'metric'
                            }
                        )
                        if forecast_response.status_code == 200:
                            forecast_data = forecast_response.json()
                            for item in forecast_data['list']:
                                forecast_date = datetime.strptime(item['dt_txt'].split()[0], '%Y-%m-%d')
                                if forecast_date.date() == current_date_ptr.date():
                                    historical_data.append({
                                        'date': current_date_ptr.strftime('%Y-%m-%d'),
                                        'temp': item['main']['temp'],
                                        'feels_like': item['main']['feels_like'],
                                        'humidity': item['main']['humidity'],
                                        'wind_speed': item['wind']['speed'],
                                        'description': item['weather'][0]['description'],
                                        'icon': item['weather'][0]['icon']
                                    })
                                    break

                except Exception as e:
                    print(f"Error processing date {current_date_ptr}: {str(e)}")
                
                current_date_ptr += timedelta(days=1)

            # Update the record
            record.location = data['location']
            record.weather_data = json.dumps({'historical': historical_data})
            
            db.session.commit()
            return jsonify({"message": "Record updated successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/weather/record/<int:id>', methods=['DELETE'])
def delete_weather_record(id):
    try:
        record = WeatherRecord.query.get_or_404(id)
        db.session.delete(record)
        db.session.commit()
        return jsonify({"message": "Record deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/forecast', methods=['GET'])
def get_forecast():
    location = request.args.get('location')
    query_params = {'q': location, 'appid': API_KEY, 'units': 'metric'} if location else None

    if not query_params:
        return jsonify({"error": "Location is required."}), 400

    try:
        response = requests.get(FORECAST_API_URL, params=query_params)
        if response.status_code != 200:
            return jsonify({"error": "Unable to fetch forecast data. Check the location."}), response.status_code

        forecast_data = response.json()
        
        # Group forecast by day and calculate daily averages
        daily_forecasts = {}
        for item in forecast_data['list']:
            date = item['dt_txt'].split()[0]  # Get just the date part
            if date not in daily_forecasts:
                daily_forecasts[date] = {
                    'temps': [],
                    'conditions': []
                }
            daily_forecasts[date]['temps'].append(item['main']['temp'])
            daily_forecasts[date]['conditions'].append(item['weather'][0]['description'])

        # Create list of daily forecasts
        forecast_list = []
        for date, data in list(daily_forecasts.items())[:5]:  # Get first 5 days
            forecast_list.append({
                "datetime": date,
                "temperature": sum(data['temps']) / len(data['temps']),  # Average temperature
                "condition": max(set(data['conditions']), key=data['conditions'].count)  # Most common condition
            })

        return jsonify({"forecast": forecast_list})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/info', methods=['GET'])
def info():
    return jsonify({
        "author": "Jefferson Chen",
        "description": "This is a weather app for the PM Accelerator assessment. Visit PM Accelerator's LinkedIn page: https://www.linkedin.com/company/product-manager-accelerator/"
    })

@app.route('/api/youtube')
def get_youtube_videos():
    try:
        location = request.args.get('location')
        if not location:
            return jsonify({'error': 'Location is required'}), 400

        # Clean up the location string for better search results
        if ',' in location:
            # If it's coordinates, try to get the city name from reverse geocoding
            try:
                lat, lon = map(float, location.split(','))
                geo_response = requests.get(
                    f"http://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={API_KEY}"
                )
                if geo_response.status_code == 200 and geo_response.json():
                    location = geo_response.json()[0].get('name', location)
            except:
                pass

        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        search_response = youtube.search().list(
            q=f"travel guide {location}",
            part='id,snippet',
            maxResults=4,
            type='video'
        ).execute()

        # Format the response
        videos = []
        for item in search_response.get('items', []):
            if item['id']['kind'] == 'youtube#video':
                videos.append({
                    'id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'thumbnail': item['snippet']['thumbnails']['medium']['url'],
                    'description': item['snippet']['description']
                })

        return jsonify({'items': videos})

    except HttpError as e:
        app.logger.error(f"YouTube API error: {str(e)}")
        return jsonify({'error': 'YouTube API error', 'details': str(e)}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error in YouTube API: {str(e)}")
        return jsonify({'error': 'Unexpected error', 'details': str(e)}), 500

@app.route('/api/wikipedia')
def get_wikipedia_info():
    location = request.args.get('location')
    try:
        page = wikipedia.page(location)
        return jsonify({
            'title': page.title,
            'extract': page.summary,
            'url': page.url
        })
    except:
        return jsonify({
            'title': location,
            'extract': 'No Wikipedia information found.',
            'url': ''
        })

def calculate_average_temperature(historical_data):
    """Calculate average temperature from historical data"""
    if not historical_data:
        return 0
    
    temperatures = [day['temp'] for day in historical_data]
    return round(sum(temperatures) / len(temperatures), 1)

@app.route('/export/<format>')
def export_data(format):
    try:
        records = WeatherRecord.query.all()
        
        if format == 'csv':
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(['Location', 'Start Date', 'End Date', 'Average Temperature (°C)'])
            
            for record in records:
                weather_data = json.loads(record.weather_data)
                historical_data = weather_data.get('historical', [])
                avg_temp = calculate_average_temperature(historical_data)
                
                writer.writerow([
                    record.location,
                    record.start_date.strftime('%Y-%m-%d'),
                    record.end_date.strftime('%Y-%m-%d'),
                    avg_temp
                ])
            
            output.seek(0)
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': 'attachment;filename=weather_records.csv'}
            )
            
        elif format == 'pdf':
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, 'Weather Records', 0, 1, 'C')
            
            pdf.set_font('Arial', '', 12)
            for record in records:
                weather_data = json.loads(record.weather_data)
                historical_data = weather_data.get('historical', [])
                avg_temp = calculate_average_temperature(historical_data)
                
                pdf.cell(0, 10, f"Location: {record.location}", 0, 1)
                pdf.cell(0, 10, f"Date Range: {record.start_date.strftime('%Y-%m-%d')} to {record.end_date.strftime('%Y-%m-%d')}", 0, 1)
                pdf.cell(0, 10, f"Average Temperature: {avg_temp}°C", 0, 1)
                pdf.cell(0, 10, '', 0, 1)  # Empty line
            
            return Response(
                pdf.output(dest='S').encode('latin-1'),
                mimetype='application/pdf',
                headers={'Content-Disposition': 'attachment;filename=weather_records.pdf'}
            )
            
        else:
            return jsonify({'error': 'Unsupported format'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize database
    with app.app_context():
        db.drop_all()
        db.create_all()
    app.run(debug=True)
