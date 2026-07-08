// Gera o hash scrypt de uma senha para a env APP_LOGIN_PASSWORD_HASH.
// Uso:  node scripts/hash-password.mjs 'minha-senha-forte'
// Copie a saida (scrypt$<salt>$<hash>) para o .env / secrets da Vercel.

import { scrypt, randomBytes } from "crypto";

const password = process.argv[2];
if (!password) {
  console.error("Uso: node scripts/hash-password.mjs 'sua-senha'");
  process.exit(1);
}

const salt = randomBytes(16);
scrypt(password, salt, 32, (err, key) => {
  if (err) throw err;
  process.stdout.write(`scrypt$${salt.toString("hex")}$${key.toString("hex")}\n`);
});
