import bcrypt from "bcryptjs";

export const hashString = (str: string, rounds?: number) => {
  return bcrypt.hashSync(str, rounds || 10);
};
