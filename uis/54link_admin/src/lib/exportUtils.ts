import * as XLSX from 'xlsx';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

export function exportToExcel(data: any[], filename: string) {
  const worksheet = XLSX.utils.json_to_sheet(data);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, 'Data');
  XLSX.writeFile(workbook, `${filename}.xlsx`);
}

export function exportToPDF(data: any[], columns: string[], filename: string, title: string) {
  const doc = new jsPDF();
  
  // Add title
  doc.setFontSize(18);
  doc.text(title, 14, 20);
  
  // Add date
  doc.setFontSize(10);
  doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 28);
  
  // Prepare table data
  const headers = [columns];
  const rows = data.map(row => columns.map(col => row[col] || ''));
  
  // Add table
  autoTable(doc, {
    head: headers,
    body: rows,
    startY: 35,
    theme: 'grid',
    headStyles: { fillColor: [37, 99, 235] },
  });
  
  doc.save(`${filename}.pdf`);
}
