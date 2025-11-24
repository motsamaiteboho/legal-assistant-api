from app.config.config import Config

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def validate_file_size(file):
    """Validate file size for FastAPI UploadFile"""
    # Save current position
    current_position = file.tell()
    
    # Seek to end to get size
    file.seek(0, 2)
    file_size = file.tell()
    
    # Reset to original position
    file.seek(current_position)
    
    return file_size <= Config.MAX_FILE_SIZE