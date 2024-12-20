# app.py
import os
import edge_tts
import asyncio
import logging
from flask import Flask, render_template, request, send_from_directory, jsonify
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure static folder for generated audio
AUDIO_DIR = 'generated_audio'
os.makedirs(AUDIO_DIR, exist_ok=True)

# Try to set proper permissions
try:
    os.chmod(AUDIO_DIR, 0o755)
except Exception as e:
    logger.error(f"Could not set permissions on audio directory: {str(e)}")

# Voice configuration dictionary
voices = {
    # English Voices (Categorized by Region)
    'United States': {
        'Emma (US)': {
            'voice_id': 'en-US-EmmaNeural',
            'styles': ['default', 'cheerful', 'sad', 'excited']
        },
        'Jenny (US)': {
            'voice_id': 'en-US-JennyNeural',
            'styles': ['default', 'chat', 'customerservice']
        },
        'Guy (US)': {
            'voice_id': 'en-US-GuyNeural',
            'styles': ['default']
        },
        'Aria (US)': {
            'voice_id': 'en-US-AriaNeural',
            'styles': ['default']
        },
        'Davis (US)': {
            'voice_id': 'en-US-DavisNeural',
            'styles': ['default']
        }
    },
    'United Kingdom': {
        'Jane (UK)': {
            'voice_id': 'en-GB-SoniaNeural',
            'styles': ['default']
        },
        'Ryan (UK)': {
            'voice_id': 'en-GB-RyanNeural',
            'styles': ['default']
        }
    },
    'Australia': {
        'Libby (AU)': {
            'voice_id': 'en-AU-NatashaNeural',
            'styles': ['default']
        },
        'William (AU)': {
            'voice_id': 'en-AU-WilliamNeural',
            'styles': ['default']
        }
    },
    # ... (rest of your voices dictionary)
}

def cleanup_old_files():
    """Clean up files older than 24 hours"""
    try:
        current_time = datetime.now()
        for filename in os.listdir(AUDIO_DIR):
            filepath = os.path.join(AUDIO_DIR, filename)
            file_time = datetime.fromtimestamp(os.path.getctime(filepath))
            if (current_time - file_time).days >= 1:
                os.remove(filepath)
                logger.info(f"Cleaned up old file: {filename}")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")

@app.before_request
def before_request():
    """Run cleanup before each request"""
    cleanup_old_files()

@app.route('/')
def index():
    try:
        flat_voices = {}
        for category, voice_group in voices.items():
            flat_voices.update(voice_group)
        return render_template('index.html', voices=flat_voices)
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/generate_audio', methods=['POST'])
async def generate_audio():
    try:
        # Get basic parameters
        text = request.form.get('text')
        selected_voice = request.form.get('voice')
        selected_style = request.form.get('style', 'default')
        
        # Get additional TTS parameters with defaults
        rate = request.form.get('rate', '+0%')
        volume = request.form.get('volume', '+0%')
        pitch = request.form.get('pitch', '+0Hz')
        
        if not text or not selected_voice:
            return jsonify({
                'error': 'Please provide text and select a voice.',
                'success': False
            })
        
        # Find voice ID
        voice_id = None
        for category in voices.values():
            if selected_voice in category:
                voice_info = category[selected_voice]
                voice_id = voice_info['voice_id']
                break
        
        if not voice_id:
            return jsonify({
                'error': 'Selected voice not found.',
                'success': False
            })
        
        # Apply style if selected
        if selected_style != 'default':
            voice_id = f"{voice_id}(Style:{selected_style})"
        
        # Create unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        audio_filename = f"{selected_voice.replace(' ', '_')}_{timestamp}_{hash(text)}_{rate}_{volume}_{pitch}.mp3"
        audio_filepath = os.path.join(AUDIO_DIR, audio_filename)
        
        logger.debug(f"Generating audio: {audio_filepath}")
        
        # Create communicate instance with parameters
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate,
            volume=volume,
            pitch=pitch
        )
        
        await communicate.save(audio_filepath)
        logger.debug(f"Audio generated successfully")
        
        return jsonify({
            'success': True,
            'audio_path': f'/generated_audio/{audio_filename}',
            'filename': audio_filename,
            'parameters': {
                'rate': rate,
                'volume': volume,
                'pitch': pitch
            }
        })
    
    except Exception as e:
        logger.error(f"Error generating audio: {str(e)}")
        return jsonify({
            'error': str(e),
            'success': False
        })

@app.route('/generated_audio/<filename>')
def serve_audio(filename):
    try:
        filepath = os.path.join(AUDIO_DIR, filename)
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return jsonify({'error': 'Audio file not found'}), 404
            
        return send_from_directory(AUDIO_DIR, filename)
    except Exception as e:
        logger.error(f"Error serving audio: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download_audio/<filename>')
def download_audio(filename):
    try:
        filepath = os.path.join(AUDIO_DIR, filename)
        if not os.path.exists(filepath):
            logger.error(f"File not found for download: {filepath}")
            return jsonify({'error': 'Audio file not found'}), 404
            
        return send_from_directory(AUDIO_DIR, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading audio: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/voice_features/<voice_name>')
def get_voice_features(voice_name):
    try:
        for category in voices.values():
            if voice_name in category:
                voice_info = category[voice_name]
                return jsonify({
                    'voice_id': voice_info['voice_id'],
                    'styles': voice_info['styles'],
                    'rate_range': {'min': '-100%', 'max': '+100%', 'default': '+0%'},
                    'volume_range': {'min': '-100%', 'max': '+100%', 'default': '+0%'},
                    'pitch_range': {'min': '-100Hz', 'max': '+100Hz', 'default': '+0Hz'}
                })
        return jsonify({'error': 'Voice not found'}), 404
    except Exception as e:
        logger.error(f"Error getting voice features: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    try:
        # Check if audio directory exists and is writable
        if not os.path.exists(AUDIO_DIR):
            return jsonify({
                'status': 'error',
                'message': 'Audio directory does not exist'
            })
        
        # Test write permissions
        test_file = os.path.join(AUDIO_DIR, 'test.txt')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Audio directory not writable: {str(e)}'
            })
            
        return jsonify({
            'status': 'healthy',
            'audio_dir': AUDIO_DIR,
            'edge_tts_version': edge_tts.__version__
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
