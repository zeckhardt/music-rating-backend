import base64
import os
import firebase_admin
import requests
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, request, abort
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['ENV'] = os.getenv('FLASK_ENV')
spotify_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_secret = os.getenv('SPOTIFY_CLIENT_SECRET')

cred = credentials.Certificate('./firebase-key.json')
firebase_admin.initialize_app(cred)

db = firestore.client()


@app.route('/album', methods=['GET'])
def get_all_albums():
    try:
        docs = db.collection('prod-ratings').stream()

        albums = [doc.to_dict() for doc in docs]

        return jsonify(albums), 200
    except Exception as e:
        return {f'[Error] Could retrieve albums: {e}'}, 500


@app.route('/album/by-artist/<string:artist_name>', methods=['GET'])
def get_artist_albums(artist_name: str):
    try:
        query = db.collection('prod-ratings').where('artistName', '==', artist_name)
        docs = query.stream()

        albums = [doc.to_dict() for doc in docs]

        if not albums:
            abort(404, 'error artist does not exist')

        return jsonify(albums), 200
    except Exception as e:
        return {f'[Error] Could retrieve albums: {e}'}, 500


@app.route('/album', methods=['POST'])
def add_rating():
    data = request.get_json()

    if not data:
        abort(400, '[Error] please specify request body')

    try:
        result = db.collection('prod-ratings').add(data)

        if not result:
            abort(400, '[Error] item could not be added to database')

        return jsonify('Data successfully added'), 200
    except Exception as e:
        return {f'[Error] Could add album: {e}'}, 500


@app.route('/album', methods=['PUT'])
def update_rating():
    data = request.get_json()

    if not data:
        abort(400, '[Error] please specify request body')

    query = db.collection('prod-ratings').where('albumName', '==', data['name'])

    try:
        docs = query.stream()
        updated = False

        for doc in docs:
            doc.reference.update({
                'albumRating': data['rating'],
                'albumReview': data['review']
            })

            updated = True

        if updated:
            return 'Album successfully updated', 200
        else:
            abort(404, '[Error] Album could not be updated')
    except Exception as e:
        return {f'[Error] Could update album: {e}'}, 500


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
