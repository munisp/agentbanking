import {
  buildTransactionReceiptHTML,
  buildOrderReceiptHTML,
  printHTML,
  shareHTMLAsPDF,
  printTransactionReceipt,
  shareTransactionReceipt,
  printOrderReceipt,
  shareOrderReceipt,
} from '../../src/services/receiptService';

jest.mock('expo-print', () => ({
  printAsync: jest.fn().mockResolvedValue(undefined),
  printToFileAsync: jest.fn().mockResolvedValue({ uri: '/tmp/receipt.pdf' }),
}));

jest.mock('expo-sharing', () => ({
  isAvailableAsync: jest.fn().mockResolvedValue(true),
  shareAsync: jest.fn().mockResolvedValue(undefined),
}));

jest.mock('react-native-paper', () => ({
  useTheme: jest.fn(() => ({ colors: { primary: '#0066FF' } })),
}));

describe('receiptService', () => {
  describe('buildTransactionReceiptHTML', () => {
    const baseTxn = {
      amount: 5000,
      type: 'cashin',
      timestamp: '2024-01-15T10:30:00Z',
      reference: 'REF-001',
      agentName: 'John Agent',
    };

    it('includes the formatted amount', () => {
      const html = buildTransactionReceiptHTML(baseTxn);

      expect(html).toContain('5,000');
    });

    it('shows DEPOSIT SUCCESSFUL for cashin type', () => {
      const html = buildTransactionReceiptHTML({ ...baseTxn, type: 'cashin' });

      expect(html).toContain('DEPOSIT SUCCESSFUL');
    });

    it('shows WITHDRAWAL SUCCESSFUL for cashout type', () => {
      const html = buildTransactionReceiptHTML({ ...baseTxn, type: 'cashout' });

      expect(html).toContain('WITHDRAWAL SUCCESSFUL');
    });

    it('shows TRANSFER SUCCESSFUL for other types', () => {
      const html = buildTransactionReceiptHTML({ ...baseTxn, type: 'transfer' });

      expect(html).toContain('TRANSFER SUCCESSFUL');
    });

    it('includes reference number', () => {
      const html = buildTransactionReceiptHTML(baseTxn);

      expect(html).toContain('REF-001');
    });

    it('masks card number showing only last 4 digits', () => {
      const html = buildTransactionReceiptHTML({ ...baseTxn, cardNumber: '4111111111111234' });

      expect(html).toContain('**** **** **** 1234');
      expect(html).not.toContain('411111111111');
    });

    it('includes agent name', () => {
      const html = buildTransactionReceiptHTML(baseTxn);

      expect(html).toContain('John Agent');
    });

    it('omits card section when no cardNumber', () => {
      const html = buildTransactionReceiptHTML(baseTxn);

      expect(html).not.toContain('****');
    });

    it('includes description when provided', () => {
      const html = buildTransactionReceiptHTML({ ...baseTxn, description: 'School fees' });

      expect(html).toContain('School fees');
    });

    it('includes agentId when provided', () => {
      const html = buildTransactionReceiptHTML({ ...baseTxn, agentId: 'AGT-999' });

      expect(html).toContain('AGT-999');
    });

    it('returns valid HTML structure', () => {
      const html = buildTransactionReceiptHTML(baseTxn);

      expect(html).toContain('<!DOCTYPE html>');
      expect(html).toContain('</html>');
      expect(html).toContain('54agent');
    });
  });

  describe('buildOrderReceiptHTML', () => {
    const baseOrder = {
      store_name: 'My Store',
      items: [
        { item_name: 'Widget', quantity: 2, subtotal: 2000 },
        { item_name: 'Gadget', quantity: 1, subtotal: 3000 },
      ],
      subtotal: 5000,
      tax: 375,
      total: 5375,
      payment_method: 'card',
      id: 'ORD-001',
      created_by: 'Agent Smith',
    };

    it('includes store name', () => {
      const html = buildOrderReceiptHTML(baseOrder);

      expect(html).toContain('MY STORE');
    });

    it('includes all item names', () => {
      const html = buildOrderReceiptHTML(baseOrder);

      expect(html).toContain('Widget');
      expect(html).toContain('Gadget');
    });

    it('includes total amount', () => {
      const html = buildOrderReceiptHTML(baseOrder);

      expect(html).toContain('5,375');
    });

    it('includes payment method', () => {
      const html = buildOrderReceiptHTML(baseOrder);

      expect(html).toContain('CARD');
    });

    it('includes order id', () => {
      const html = buildOrderReceiptHTML(baseOrder);

      expect(html).toContain('ORD-001');
    });

    it('includes customer info when provided', () => {
      const html = buildOrderReceiptHTML({ ...baseOrder, customer_name: 'Jane Doe', customer_phone: '08012345678' });

      expect(html).toContain('Jane Doe');
      expect(html).toContain('08012345678');
    });

    it('handles empty items array', () => {
      const html = buildOrderReceiptHTML({ ...baseOrder, items: [] });

      expect(html).toContain('<!DOCTYPE html>');
    });
  });

  describe('printHTML', () => {
    it('calls Print.printAsync with html', async () => {
      const { printAsync } = require('expo-print');
      await printHTML('<html>test</html>');

      expect(printAsync).toHaveBeenCalledWith({ html: '<html>test</html>' });
    });
  });

  describe('shareHTMLAsPDF', () => {
    it('creates PDF and shares it', async () => {
      const { printToFileAsync } = require('expo-print');
      const { shareAsync } = require('expo-sharing');

      await shareHTMLAsPDF('<html>receipt</html>', 'receipt.pdf');

      expect(printToFileAsync).toHaveBeenCalledWith({ html: '<html>receipt</html>', base64: false });
      expect(shareAsync).toHaveBeenCalledWith('/tmp/receipt.pdf', expect.objectContaining({ mimeType: 'application/pdf' }));
    });

    it('throws when sharing is not available', async () => {
      const { isAvailableAsync } = require('expo-sharing');
      isAvailableAsync.mockResolvedValueOnce(false);

      await expect(shareHTMLAsPDF('<html/>', 'file.pdf')).rejects.toThrow('Sharing is not available');
    });
  });

  describe('printTransactionReceipt', () => {
    it('calls printAsync with generated HTML', async () => {
      const { printAsync } = require('expo-print');
      const txn = { amount: 1000, type: 'cashin', timestamp: Date.now(), reference: 'REF' };

      await printTransactionReceipt(txn);

      expect(printAsync).toHaveBeenCalled();
      const html = printAsync.mock.calls[0][0].html;
      expect(html).toContain('54agent');
    });
  });

  describe('shareTransactionReceipt', () => {
    it('shares receipt PDF with reference-based filename', async () => {
      const { shareAsync } = require('expo-sharing');
      const txn = { amount: 2000, type: 'cashout', timestamp: Date.now(), reference: 'TXN-ABC' };

      await shareTransactionReceipt(txn);

      expect(shareAsync).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ mimeType: 'application/pdf' })
      );
    });
  });

  describe('printOrderReceipt', () => {
    it('calls printAsync with order HTML', async () => {
      const { printAsync } = require('expo-print');
      const order = { items: [], subtotal: 0, tax: 0, total: 0 };

      await printOrderReceipt(order);

      expect(printAsync).toHaveBeenCalled();
    });
  });

  describe('shareOrderReceipt', () => {
    it('shares order PDF', async () => {
      const { shareAsync } = require('expo-sharing');
      const order = { id: 'ORD-1', items: [], subtotal: 0, tax: 0, total: 0 };

      await shareOrderReceipt(order);

      expect(shareAsync).toHaveBeenCalled();
    });
  });
});
