// js/playlists.js
import { supabase } from './supabase.js';

export async function createPlaylist(name, trackIds = []) {
  try {
    const { data: { user }, error: userErr } = await supabase.auth.getUser();
    if (userErr || !user) throw new Error('Usuario no autenticado');

    const { data, error } = await supabase
      .from('playlists')
      .insert([{ name, user_id: user.id, tracks: trackIds }])
      .select();

    if (error) throw error;
    return data;
  } catch (err) {
    console.error('Error al crear playlist:', err.message);
    throw err;
  }
}