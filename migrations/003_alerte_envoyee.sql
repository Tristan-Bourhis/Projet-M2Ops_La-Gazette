-- Migration 003 : un contrôle rouge n'est « déjà signalé » que si l'alerte est bien partie.
-- Sans cette colonne, une alerte ratée (pas de .env, webhook injoignable) n'était jamais renvoyée.
ALTER TABLE controles_qualite ADD COLUMN alerte_envoyee boolean NOT NULL DEFAULT false;
