-- Tags RPCs
-- Read tags for current user
CREATE OR REPLACE FUNCTION public.tags_read() RETURNS SETOF public.tags LANGUAGE sql STABLE AS $$
SELECT *
FROM public.tags
WHERE user_id = auth.uid()
ORDER BY name;
$$;
-- Create a tag
CREATE OR REPLACE FUNCTION public.tags_create(p_name text, p_color text DEFAULT NULL) RETURNS public.tags LANGUAGE sql AS $$
INSERT INTO public.tags (user_id, name, color)
VALUES (auth.uid(), p_name, p_color) ON CONFLICT (user_id, name) DO
UPDATE
SET color = EXCLUDED.color
RETURNING *;
$$;
-- Update a tag
CREATE OR REPLACE FUNCTION public.tags_update(
        p_id uuid,
        p_name text DEFAULT NULL,
        p_color text DEFAULT NULL
    ) RETURNS public.tags LANGUAGE plpgsql AS $$
DECLARE _row public.tags %ROWTYPE;
BEGIN
UPDATE public.tags
SET name = COALESCE(p_name, name),
    color = COALESCE(p_color, color)
WHERE id = p_id
    AND user_id = auth.uid();
SELECT * INTO _row
FROM public.tags
WHERE id = p_id;
RETURN _row;
END;
$$;
-- Delete a tag
CREATE OR REPLACE FUNCTION public.tags_delete(p_id uuid) RETURNS void LANGUAGE sql AS $$
DELETE FROM public.tags
WHERE id = p_id
    AND user_id = auth.uid();
$$;