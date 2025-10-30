-- Activity log helper (optional)
CREATE OR REPLACE FUNCTION public.activity_log_create(
        p_task_id uuid,
        p_action text,
        p_before jsonb DEFAULT NULL,
        p_after jsonb DEFAULT NULL
    ) RETURNS void LANGUAGE sql AS $$
INSERT INTO public.task_activity_log (
        task_id,
        user_id,
        action,
        before_data,
        after_data
    )
VALUES (
        p_task_id,
        auth.uid(),
        p_action,
        p_before,
        p_after
    );
$$;