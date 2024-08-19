import json

from flask import Flask, g, jsonify, request, abort
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError
import requests
import certifi
import base64
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

MONGO_URI = os.getenv('DATABASE_URI')
app.config['ENV'] = os.getenv('FLASK_ENV')
spotify_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_secret = os.getenv('SPOTIFY_CLIENT_SECRET')


def get_db():
    if 'db' not in g:
        g.db = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        g.db = g.db['musicData']
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.client.close()


def get_collection(name: str):
    db = get_db()
    return db[name]


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


@app.route('/album', methods=['GET'])
def get_all_albums():
    collection = get_collection('musicRating')
    try:
        cursor = collection.find({})
        data = list(cursor)
        if not data:
            abort(404, 'error no ratings could be found')
        return json.dumps(data, default=str), 200
    except PyMongoError as e:
        return jsonify({'error': e}), 500


@app.route('/album/by-artist/<string:artist_name>', methods=['GET'])
def get_artist_albums(artist_name: str):
    collection = get_collection('musicRating')
    try:
        cursor = collection.find({'artistName': artist_name})
        albums = list(cursor)
        if not albums:
            abort(404, 'error artist does not exist')
        return json.dumps(albums, default=str), 200
    except PyMongoError as e:
        return jsonify({'error': e}), 500


@app.route('/album', methods=['POST'])
def add_rating():
    data = request.get_json()
    if not data:
        abort(400, 'error please specify request body')

    try:
        collection = get_collection('musicRating')
        result = collection.insert_one(data)

        if not result:
            abort(400, 'error item could not be added to database')
        return jsonify('Data successfully added'), 200
    except PyMongoError as e:
        return jsonify({'error': e}), 500


@app.route('/album', methods=['PUT'])
def update_rating():
    collection = get_collection('musicRating')
    data = request.get_json()
    if not data:
        abort(400, 'error please specify request body')

    query = {'albumName': data['name']}
    new_values = {
        '$set': {
            'albumRating': data['rating'],
            'albumReview': data['review']
        }
    }

    try:
        result = collection.update_one(query, new_values)
        if result.matched_count > 0:
            return 200
        else:
            abort(404, 'error the item could not be update (not found)')
    except PyMongoError as e:
        return jsonify({'error': str(e)}), 500


def get_access_token():
    params = {
        'grant_type': 'client_credentials'
    }
    auth_str = f'{spotify_id}:{spotify_secret}'
    auth_bytes = auth_str.encode('utf-8')
    auth_base64 = base64.b64encode(auth_bytes).decode('utf-8')

    headers = {
        'Authorization': f'Basic {auth_base64}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    response = requests.post('https://accounts.spotify.com/api/token', data=params, headers=headers)

    if response.status_code == 200:
        token = response.json()
        return token['access_token']
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None


@app.route('/spotify/<string:artist_id>')
def get_albums(artist_id: str):
    headers = {
        'Authorization': 'Bearer ' + get_access_token(),
        'Content-Type': 'application-json'
    }

    response = requests.get(f'https://api.spotify.com/v1/artists/{str(artist_id)}/albums?limit=30&offset=0', headers=headers)

    if response.status_code == 200:
        return response.json()['items']
    else:
        return None


@app.route('/spotify/artists/<string:artist_name>')
def get_artists(artist_name: str):
    headers = {
        'Authorization': 'Bearer ' + get_access_token(),
        'Content-Type': 'application-json'
    }

    response = requests.get(f'https://api.spotify.com/v1/search?q=artist%3A{artist_name}&type=artist', headers=headers)
    if response.status_code == 200:
        return response.json()


if __name__ == '__main__':
    app.run()
