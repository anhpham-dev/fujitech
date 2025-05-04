import hashlib
import base64
import re

def generate_license_key(discord_user_id, product_name):
    """
    Generate a unique license key in the format ####-####-####-####
    based on a Discord user ID and product name.
    
    Args:
        discord_user_id (str): The Discord user ID
        product_name (str): The name of the product
        
    Returns:
        str: License key in the format ####-####-####-####
    """
    # Combine the user ID and product name
    combined = f"{discord_user_id}:{product_name}"
    
    # Create a hash of the combined string
    hash_obj = hashlib.sha256(combined.encode())
    hash_digest = hash_obj.digest()
    
    # Convert the hash to a base64 string and remove non-alphanumeric characters
    b64_str = base64.b64encode(hash_digest).decode('utf-8')
    clean_str = re.sub(r'[^A-Z0-9]', '', b64_str.upper())
    
    # Ensure we have enough characters
    if len(clean_str) < 16:
        # Cycle through the string to get enough characters
        clean_str = clean_str * (16 // len(clean_str) + 1)
    
    # Take the first 16 characters
    key_str = clean_str[:16]
    
    # Format into ####-####-####-####
    formatted_key = f"{key_str[0:4]}-{key_str[4:8]}-{key_str[8:12]}-{key_str[12:16]}"
    
    return formatted_key

def verify_license_key(license_key, discord_user_id, product_name):
    """
    Verify if a license key is valid for a given Discord user ID and product name.
    
    Args:
        license_key (str): The license key to verify
        discord_user_id (str): The Discord user ID
        product_name (str): The name of the product
        
    Returns:
        bool: True if the license key is valid, False otherwise
    """
    # Generate the expected license key
    expected_key = generate_license_key(discord_user_id, product_name)
    
    # Compare with the provided license key (ignoring case)
    return license_key.upper() == expected_key.upper()

# Example usage
if __name__ == "__main__":
    # Generate a license key
    discord_id = "123456789012345678"
    product = "ThePetlingoBot"
    license_key = generate_license_key(discord_id, product)
    print(f"License key for user {discord_id}, product {product}: {license_key}")
    
    # Verify the license key
    is_valid = verify_license_key(license_key, discord_id, product)
    print(f"License key verification: {is_valid}")
    
    # Example with an invalid key
    fake_key = "ABCD-1234-EFGH-5678"
    is_valid = verify_license_key(fake_key, discord_id, product)
    print(f"Fake key verification: {is_valid}")