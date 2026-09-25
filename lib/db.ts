import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";

const DB_PATH = process.env.DATABASE_PATH ?? path.join(process.cwd(), "data", "sud.db");

declare global {
  // eslint-disable-next-line no-var
  var __sudDb: Database.Database | undefined;
}

function open(): Database.Database {
  fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
  const db = new Database(DB_PATH);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  db.exec(fs.readFileSync(path.join(process.cwd(), "lib", "schema.sql"), "utf8"));
  return db;
}

// Dev rejimida hot-reload paytida ulanish qayta ochilmasligi uchun global'da saqlanadi.
export function getDb(): Database.Database {
  if (!globalThis.__sudDb) globalThis.__sudDb = open();
  return globalThis.__sudDb;
}
