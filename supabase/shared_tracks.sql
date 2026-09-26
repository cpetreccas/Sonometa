-- ============================================================================
-- Enlaces públicos para compartir pistas (Social Card con Open Graph)
--
-- Ejecutar una vez en el SQL Editor de Supabase. Es idempotente.
--
-- Cada pista compartida recibe un token aleatorio (18 caracteres hex). La página
-- pública /t/<token> (función de Netlify) solo puede leer los datos básicos de
-- esa pista a través de get_shared_track(); el resto de la tabla tracks sigue
-- protegida por RLS. Borrar la fila de shared_tracks revoca el enlace.
-- ============================================================================

create table if not exists public.shared_tracks (
    token      text primary key default encode(extensions.gen_random_bytes(9), 'hex'),
    track_id   uuid not null unique references public.tracks(id) on delete cascade,
    user_id    uuid not null default auth.uid() references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

alter table public.shared_tracks enable row level security;

-- El dueño puede ver y revocar sus enlaces. Las altas van solo por create_track_share().
drop policy if exists "shared_tracks_owner_select" on public.shared_tracks;
create policy "shared_tracks_owner_select" on public.shared_tracks
    for select using (user_id = auth.uid());

drop policy if exists "shared_tracks_owner_delete" on public.shared_tracks;
create policy "shared_tracks_owner_delete" on public.shared_tracks
    for delete using (user_id = auth.uid());


-- Crea (o reutiliza) el enlace de una pista del usuario autenticado y devuelve el token.
create or replace function public.create_track_share(p_track_id uuid)
returns text
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    v_token text;
begin
    if auth.uid() is null then
        raise exception 'No autenticado';
    end if;

    if not exists (select 1 from tracks where id = p_track_id and user_id = auth.uid()) then
        raise exception 'Pista no encontrada';
    end if;

    insert into shared_tracks (track_id, user_id)
    values (p_track_id, auth.uid())
    on conflict (track_id) do nothing;

    select token into v_token from shared_tracks where track_id = p_track_id;
    return v_token;
end;
$$;

revoke all on function public.create_track_share(uuid) from public, anon;
grant execute on function public.create_track_share(uuid) to authenticated;


-- Lectura pública: solo los campos que muestra la tarjeta (sin rating, comentarios,
-- rutas locales ni usuario).
create or replace function public.get_shared_track(p_token text)
returns table (
    title      text,
    artist     text,
    mix_artist text,
    album      text,
    genre      text,
    publisher  text,
    year       text,
    duration   varchar,
    cover_url  text
)
language sql
stable
security definer
set search_path = public
as $$
    select t.title, t.artist, t.mix_artist, t.album, t.genre, t.publisher,
           t.year, t.duration, t.cover_url
    from shared_tracks s
    join tracks t on t.id = s.track_id
    where s.token = p_token;
$$;

revoke all on function public.get_shared_track(text) from public;
grant execute on function public.get_shared_track(text) to anon, authenticated;
