from flask import Flask, render_template, request, send_file, jsonify
from datetime import datetime
import requests
import pandas as pd
import numpy as np
import io
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Get API key from environment variables
API_KEY = os.getenv('BITGET_API_KEY')
if not API_KEY:
    print("Warning: BITGET_API_KEY not found in environment variables")


def unix_timestamp(date_str, is_end_date=False):
    """Convert date string to unix timestamp in milliseconds"""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')

        if is_end_date:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)

        timestamp = int(dt.timestamp() * 1000)

        print(f"Converting {'end' if is_end_date else 'start'} date: {dt.strftime('%Y-%m-%d %H:%M:%S.%f')}")
        print(f"Timestamp: {timestamp}")

        return timestamp

    except Exception as e:
        raise Exception(f"Error converting date: {str(e)}")

def fetch_bitget_data(symbol, start_ts, end_ts, interval='1d'):
    """Fetch historical candle data from Bitget"""
    try:
        base_url = "https://api.bitget.com/api/v2/spot/market/history-candles"

        # Updated granularity map with available values from Bitget documentation
        interval_map = {
            '1m': '1min',
            '5m': '5min',
            '15m': '15min',
            '30m': '30min',
            '1h': '1h',
            '4h': '4h',
            '6h': '6h',
            '12h': '12h',
            '1d': '1day',
            '3d': '3day',
            '1w': '1week',
            '1M': '1M',
            '6h_utc': '6Hutc',
            '12h_utc': '12Hutc',
            '1d_utc': '1Dutc',
            '3d_utc': '3Dutc',
            '1w_utc': '1Wutc',
            '1M_utc': '1Mutc'
        }

        # Construct parameters for the request
        params = {
            "symbol": symbol,
            "granularity": interval_map.get(interval, '1day'),  # Default to '1day' if interval is not in map
            "startTime": str(start_ts),  # Convert start time to string
            "endTime": str(end_ts),  # Convert end time to string
            "limit": 100
        }

        headers = {
            'ACCESS-KEY': API_KEY  # Add your API key to headers if required by the Bitget API
        }

        # Make the GET request to the API
        response = requests.get(base_url, params=params, headers=headers)

        # Debug print to verify the request
        print(f"API Request URL: {response.url}")

        # Handle the response
        if response.status_code != 200:
            raise Exception(f"API Error: {response.text}")

        data = response.json()

        # Check for the success code in the response
        if data.get('code') != '00000':
            raise Exception(f"Bitget API Error: {data.get('msg')}")

        # Parse the response data
        columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'quote_volume', 'extra_volume']
        df = pd.DataFrame(data.get('data', []), columns=columns)

        # Additional data processing if data exists
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'].astype(np.int64), unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'extra_volume']:
                df[col] = df[col].astype(float)
            df = df.sort_values('timestamp')

        return df

    except Exception as e:
        print(f"\nError in fetch_bitget_data: {str(e)}")
        raise

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    """Handle the download request"""
    try:
        # Get form data
        symbol = request.form['symbol'].strip().upper()
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        interval = request.form['interval']

        print("\nRequest Details:")
        print("-" * 50)
        print(f"Symbol: {symbol}")
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date}")
        print(f"Interval: {interval}")
        print("-" * 50)

        # Validate inputs
        if not symbol or not start_date or not end_date or not interval:
            raise Exception("All fields are required")

        # Convert dates to timestamps with full precision
        start_ts = unix_timestamp(start_date, is_end_date=False)
        end_ts = unix_timestamp(end_date, is_end_date=True)

        # Fetch data from Bitget
        df = fetch_bitget_data(symbol, start_ts, end_ts, interval)

        if df.empty:
            raise Exception("No data available for the specified parameters")

        # Convert to CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, date_format='%Y-%m-%d %H:%M:%S')
        csv_buffer.seek(0)

        # Generate filename
        filename = f'bitget_{symbol}_{start_date}_{end_date}.csv'

        return send_file(
            io.BytesIO(csv_buffer.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        error_msg = str(e)
        print(f"\nError occurred: {error_msg}")
        return jsonify({'error': error_msg}), 400

if __name__ == "__main__":
    # Get port from environment variable or use default
    port = int(os.getenv('PORT', 8080))

    # Print startup message
    print("\nStarting Bitget Data Downloader")
    print("-" * 50)
    print(f"Server Port: {port}")
    print(f"API Key configured: {'Yes' if API_KEY else 'No'}")
    print(f"Debug Mode: Enabled")
    print("-" * 50)

    app.run(host='0.0.0.0', port=port, debug=True)
