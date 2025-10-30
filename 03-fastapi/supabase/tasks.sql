-- Tasks RPCs
-- Read tasks for current user; optional p_list_id to filter by list
CREATE OR REPLACE FUNCTION public.tasks_read(p_list_id uuid DEFAULT NULL) RETURNS SETOF public.tasks LANGUAGE sql STABLE AS $$
SELECT *
FROM public.tasks
WHERE user_id = auth.uid()
    AND (
        p_list_id IS NULL
        OR list_id = p_list_id
    )
ORDER BY sort_order,
    created_at;
$$;
-- Create a task for current user
CREATE OR REPLACE FUNCTION public.tasks_create(
        p_title text,
        p_list_id uuid,
        p_notes text DEFAULT NULL,
        p_due_date date DEFAULT NULL,
        p_due_time time DEFAULT NULL,
        p_is_important boolean DEFAULT false,
        p_priority smallint DEFAULT 3,
        p_sort_order numeric DEFAULT 0
    ) RETURNS public.tasks LANGUAGE sql AS $$
INSERT INTO public.tasks (
        user_id,
        list_id,
        title,
        notes,
        due_date,
        due_time,
        is_important,
        priority,
        sort_order
    )
VALUES (
        auth.uid(),
        p_list_id,
        p_title,
        p_notes,
        p_due_date,
        p_due_time,
        p_is_important,
        p_priority,
        p_sort_order
    )
RETURNING *;
$$;
-- Update a task (partial update)
CREATE OR REPLACE FUNCTION public.tasks_update(
        p_id uuid,
        p_title text DEFAULT NULL,
        p_notes text DEFAULT NULL,
        p_status text DEFAULT NULL,
        p_priority smallint DEFAULT NULL,
        p_due_date date DEFAULT NULL,
        p_due_time time DEFAULT NULL,
        p_is_important boolean DEFAULT NULL,
        p_sort_order numeric DEFAULT NULL,
        p_completed_at timestamptz DEFAULT NULL
    ) RETURNS public.tasks LANGUAGE plpgsql AS $$
DECLARE _row public.tasks %ROWTYPE;
BEGIN
UPDATE public.tasks
SET title = COALESCE(p_title, title),
    notes = COALESCE(p_notes, notes),
    status = COALESCE(p_status, status),
    priority = COALESCE(p_priority, priority),
    due_date = COALESCE(p_due_date, due_date),
    due_time = COALESCE(p_due_time, due_time),
    is_important = COALESCE(p_is_important, is_important),
    sort_order = COALESCE(p_sort_order, sort_order),
    completed_at = COALESCE(p_completed_at, completed_at),
    updated_at = now()
WHERE id = p_id
    AND user_id = auth.uid();
SELECT * INTO _row
FROM public.tasks
WHERE id = p_id;
RETURN _row;
END;
$$;
-- Delete a task
CREATE OR REPLACE FUNCTION public.tasks_delete(p_id uuid) RETURNS void LANGUAGE sql AS $$
DELETE FROM public.tasks
WHERE id = p_id
    AND user_id = auth.uid();
$$;