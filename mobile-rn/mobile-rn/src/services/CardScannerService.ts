import TextRecognition from 'react-native-text-recognition';

class CardScannerService {
  async scanCard(imagePath: string) {
    try {
      const result = await TextRecognition.recognize(imagePath);
      const text = result.join(' ');
      
      return this.extractCardDetails(text);
    } catch (error) {
      console.error('Card scan failed:', error);
      throw error;
    }
  }

  private extractCardDetails(text: string) {
    const cardNumberPattern = /\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b/;
    const cardNumberMatch = text.match(cardNumberPattern);
    const cardNumber = cardNumberMatch ? cardNumberMatch[1].replace(/[\s\-]/g, '') : '';

    const expiryPattern = /\b(0[1-9]|1[0-2])[\/\-](\d{2}|\d{4})\b/;
    const expiryMatch = text.match(expiryPattern);
    const expiryDate = expiryMatch ? expiryMatch[0] : '';

    return {
      cardNumber,
      expiryDate,
      cardType: this.detectCardType(cardNumber)
    };
  }

  private detectCardType(cardNumber: string) {
    if (/^4/.test(cardNumber)) return 'visa';
    if (/^5[1-5]/.test(cardNumber)) return 'mastercard';
    if (/^3[47]/.test(cardNumber)) return 'amex';
    return 'unknown';
  }
}

export const cardScannerService = new CardScannerService();
