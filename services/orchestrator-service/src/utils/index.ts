export function generateSlug(str: string) {
  return str
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_") // replace all spaces with underscores
    .replace(/[^\w_]+/g, ""); // removes non-alphanumeric characters
}
