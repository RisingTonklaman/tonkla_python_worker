-- Lists RPCs
-- Use auth.uid() so the function operates for the calling user (pass JWT from client)
-- Read all lists for current user
CREATE OR REPLACE FUNCTION public.lists_read() RETURNS SETOF public.lists LANGUAGE sql STABLE AS $$
SELECT *
FROM public.lists
WHERE user_id = auth.uid()
ORDER BY position,
    created_at;
$$;
-- Create a list for current user
CREATE OR REPLACE FUNCTION public.lists_create(
        p_title text,
        p_color text DEFAULT NULL,
        p_position numeric DEFAULT 0
    ) RETURNS public.lists LANGUAGE sql AS $$
INSERT INTO public.lists (user_id, title, color, position)
VALUES (auth.uid(), p_title, p_color, p_position)
RETURNING *;
$$;
-- Update a list (only updates provided fields)
CREATE OR REPLACE FUNCTION public.lists_update(
        p_id uuid,
        p_title text DEFAULT NULL,
        p_color text DEFAULT NULL,
        p_is_archived boolean DEFAULT NULL,
        p_position numeric DEFAULT NULL
    ) RETURNS public.lists LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public AS $$
DECLARE _row public.lists %ROWTYPE;
BEGIN
UPDATE public.lists
SET title = COALESCE(p_title, title),
    color = COALESCE(p_color, color),
    is_archived = COALESCE(p_is_archived, is_archived),
    position = COALESCE(p_position, position),
    updated_at = now()
WHERE id = p_id
    AND user_id = auth.uid();
SELECT * INTO _row
FROM public.lists
WHERE id = p_id;
RETURN _row;
END;
$$;
-- สิทธิ์เรียกใช้ผ่าน PostgREST/Supabase
GRANT EXECUTE ON FUNCTION public.lists_update(uuid, text, text, boolean, numeric) TO anon,
    authenticated,
    service_role;
-- Delete a list (and cascade will remove tasks)
CREATE OR REPLACE FUNCTION public.lists_delete(p_id uuid) RETURNS void LANGUAGE sql AS $$
DELETE FROM public.lists
WHERE id = p_id
    AND user_id = auth.uid();
$$;