// js/auth.js
import { supabase } from './supabase.js';

export async function checkSession() {
  try {
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error) throw error;
    return session;
  } catch (err) {
    console.error('Error al verificar sesión:', err.message);
    return null;
  }
}

export async function login(email, password) {
  const cleanEmail = (email || '').trim();
  const cleanPassword = (password || '').trim();

  // Validaciones defensivas de entradas
  if (!cleanEmail || !cleanEmail.includes('@')) {
    throw new Error('Por favor, introduce un correo electrónico válido.');
  }
  if (!cleanPassword || cleanPassword.length < 6) {
    throw new Error('La contraseña debe tener al menos 6 caracteres.');
  }

  const { data, error } = await supabase.auth.signInWithPassword({
    email: cleanEmail,
    password: cleanPassword
  });

  if (error) throw new Error(error.message || 'Error en el inicio de sesión');
  return data;
}

export async function logout() {
  try {
    await supabase.auth.signOut();
    window.location.reload();
  } catch (err) {
    console.error('Error durante logout:', err);
  }
}