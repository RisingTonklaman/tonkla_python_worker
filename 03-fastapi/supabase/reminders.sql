-- Reminders RPCs
CREATE OR REPLACE FUNCTION public.reminders_create(p_task_id uuid, p_remind_at timestamptz) RETURNS public.reminders LANGUAGE sql AS $$
INSERT INTO public.reminders (task_id, user_id, remind_at)
VALUES (p_task_id, auth.uid(), p_remind_at)
RETURNING *;
$$;
CREATE OR REPLACE FUNCTION public.reminders_read() RETURNS SETOF public.reminders LANGUAGE sql STABLE AS $$
SELECT *
FROM public.reminders
WHERE user_id = auth.uid()
ORDER BY remind_at;
$$;
CREATE OR REPLACE FUNCTION public.reminders_delete(p_id uuid) RETURNS void LANGUAGE sql AS $$
DELETE FROM public.reminders
WHERE id = p_id
    AND user_id = auth.uid();
$$;