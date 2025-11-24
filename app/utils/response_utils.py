def create_success_response(data=None, message="Success"):
    """Create standardized success response"""
    response = {
        "success": True,
        "message": message
    }
    if data is not None:
        response["data"] = data
    return response

def create_error_response(message="Error", status_code=400):
    """Create standardized error response"""
    return {
        "success": False,
        "error": message
    }, status_code