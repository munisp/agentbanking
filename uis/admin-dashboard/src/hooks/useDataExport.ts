export function useDataExport() {
  return { exportToCsv: (_data: any[], _filename: string) => {}, exportToJson: (_data: any, _filename: string) => {} };
}
