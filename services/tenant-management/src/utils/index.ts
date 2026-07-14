import bcrypt from "bcryptjs";
import { SALT_ROUNDS } from "./constants";

export async function hashString(str: string) {
  return await bcrypt.hash(str, SALT_ROUNDS);
}
