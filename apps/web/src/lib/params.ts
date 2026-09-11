/** Id numérico de la URL ("42") o null si falta o no es un entero positivo. */
export function parseId(value: string | null | undefined): number | null {
  if (!value || !/^\d+$/.test(value)) return null;
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}
