import { z } from "zod";

/** Misma política que el backend (app/auth/passwords.py): bcrypt ignora lo que pase de 72 bytes. */
export const newPasswordSchema = z
  .string()
  .min(10, "Use at least 10 characters")
  .refine((value) => new TextEncoder().encode(value).length <= 72, "Use at most 72 bytes");

export const emailSchema = z.email("Enter a valid email address");

export const usernameSchema = z
  .string()
  .trim()
  .min(3, "Use at least 3 characters")
  .max(50, "Use at most 50 characters");

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Enter your password"),
});

export const registerSchema = z.object({
  username: usernameSchema,
  email: emailSchema,
  password: newPasswordSchema,
});
