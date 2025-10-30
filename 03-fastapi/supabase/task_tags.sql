-- Task tags assign/unassign
CREATE OR REPLACE FUNCTION public.task_tags_assign(p_task_id uuid, p_tag_id uuid) RETURNS void LANGUAGE sql AS $$
INSERT INTO public.task_tags (task_id, tag_id)
SELECT p_task_id,
    p_tag_id
WHERE EXISTS (
        SELECT 1
        FROM public.tasks t
        WHERE t.id = p_task_id
            AND t.user_id = auth.uid()
    )
    AND EXISTS (
        SELECT 1
        FROM public.tags g
        WHERE g.id = p_tag_id
            AND g.user_id = auth.uid()
    ) ON CONFLICT DO NOTHING;
$$;
CREATE OR REPLACE FUNCTION public.task_tags_unassign(p_task_id uuid, p_tag_id uuid) RETURNS void LANGUAGE sql AS $$
DELETE FROM public.task_tags
WHERE task_id = p_task_id
    AND tag_id = p_tag_id
    AND EXISTS (
        SELECT 1
        FROM public.tasks t
        WHERE t.id = p_task_id
            AND t.user_id = auth.uid()
    );
$$;