-- raw_events(payload JSON, source_position BIGINT) contains one match.
-- Parameters: window_seconds (nullable DOUBLE), short_limit (DOUBLE), match_id.
-- All extraction decisions are made here, independently of corners.extract.
WITH decoded AS (
    SELECT payload, source_position,
        json_extract_string(payload, '$.id') AS id,
        CAST(json_extract_string(payload, '$.period') AS BIGINT) AS period,
        json_extract_string(payload, '$.timestamp') AS timestamp,
        CAST(json_extract_string(payload, '$.index') AS BIGINT) AS provider_index,
        CAST(json_extract_string(payload, '$.possession') AS BIGINT) AS possession,
        CAST(json_extract_string(payload, '$.team.id') AS BIGINT) AS team_id,
        json_extract_string(payload, '$.type.name') AS kind
    FROM raw_events
), ordered AS (
    SELECT *,
        CAST(split_part(timestamp, ':', 1) AS BIGINT) * 3600
        + CAST(split_part(timestamp, ':', 2) AS BIGINT) * 60
        + CAST(split_part(timestamp, ':', 3) AS DOUBLE) AS seconds,
        row_number() OVER (ORDER BY period,
            CAST(split_part(timestamp, ':', 1) AS BIGINT) * 3600
            + CAST(split_part(timestamp, ':', 2) AS BIGINT) * 60
            + CAST(split_part(timestamp, ':', 3) AS DOUBLE),
            provider_index, source_position) AS seq
    FROM decoded
), events AS (
    SELECT *,
        json_extract(payload, '$.' || lower(replace(kind, ' ', '_'))) AS details,
        coalesce(CAST(json_extract_string(payload, '$.out') AS BOOLEAN), false) AS ball_out,
        json_extract_string(payload, '$.shot.outcome.name') = 'Goal' AS shot_goal
    FROM ordered
), starters AS (
    SELECT * FROM events
    WHERE kind IN ('Pass', 'Shot')
      AND json_extract_string(details, '$.type.name') = 'Corner'
    QUALIFY row_number() OVER (PARTITION BY id ORDER BY seq) = 1
), corners AS (
    SELECT *, (SELECT min(e.seq) FROM events e WHERE e.id = starters.id) AS anchor,
        CASE WHEN json_extract_string(details, '$.outcome.name') = 'Goal' THEN 'goal'
             WHEN ball_out THEN 'ball_out' END AS starter_stop,
        CASE WHEN json_array_length(json_extract(payload, '$.location')) >= 2
             THEN CAST(json_extract_string(payload, '$.location[0]') AS DOUBLE) END AS start_x,
        CASE WHEN json_array_length(json_extract(payload, '$.location')) >= 2
             THEN CAST(json_extract_string(payload, '$.location[1]') AS DOUBLE) END AS start_y,
        CASE WHEN json_array_length(json_extract(details, '$.end_location')) >= 2
             THEN CAST(json_extract_string(details, '$.end_location[0]') AS DOUBLE) END AS end_x,
        CASE WHEN json_array_length(json_extract(details, '$.end_location')) >= 2
             THEN CAST(json_extract_string(details, '$.end_location[1]') AS DOUBLE) END AS end_y
    FROM starters
), candidates AS (
    -- Seen IDs are match-local and chain-local. Global deduplication would
    -- change behavior when the same UUID occurs before and after a starter.
    SELECT c.id AS corner_id, a.*,
        CASE
            WHEN a.period <> c.period THEN 'period_end'
            WHEN $window_seconds IS NOT NULL AND a.seconds - c.seconds > $window_seconds THEN 'time_limit'
            WHEN a.kind IN ('Pass', 'Shot') AND json_extract_string(a.details, '$.type.name')
                IN ('Corner', 'Free Kick', 'Goal Kick', 'Kick Off', 'Throw-in', 'Penalty') THEN 'new_restart'
            WHEN a.possession IS DISTINCT FROM c.possession THEN 'possession_change'
            WHEN a.kind IN ('Half End', 'Injury Stoppage', 'Offside', 'Referee Ball-Drop') THEN 'stoppage'
            WHEN a.kind IN ('Foul Committed', 'Foul Won')
                AND NOT coalesce(CAST(json_extract_string(a.details, '$.advantage') AS BOOLEAN), false) THEN 'stoppage'
        END AS pre_stop
    FROM corners c JOIN events a ON a.seq > c.anchor AND a.id <> c.id
    WHERE c.starter_stop IS NULL
    QUALIFY row_number() OVER (PARTITION BY c.id, a.id ORDER BY a.seq) = 1
), boundaries AS (
    SELECT corner_id, seq, pre_stop,
        coalesce(pre_stop, CASE WHEN shot_goal THEN 'goal' WHEN ball_out THEN 'ball_out' END) AS reason
    FROM candidates
    WHERE pre_stop IS NOT NULL OR shot_goal OR ball_out
    QUALIFY row_number() OVER (PARTITION BY corner_id ORDER BY seq) = 1
), included AS (
    -- Always include the starter, even for a direct goal/out delivery.
    SELECT id AS corner_id, CAST(0 AS BIGINT) AS action_seq, id, kind,
        kind = 'Shot' AS attacking_shot,
        json_extract_string(details, '$.outcome.name') = 'Goal' AS is_goal,
        coalesce(CAST(json_extract_string(payload, '$.shot.statsbomb_xg') AS DOUBLE), 0) AS xg
    FROM corners
    UNION ALL
    SELECT a.corner_id, a.seq, a.id, a.kind, a.kind = 'Shot' AND a.team_id = c.team_id,
        a.shot_goal,
        coalesce(CAST(json_extract_string(a.payload, '$.shot.statsbomb_xg') AS DOUBLE), 0)
    FROM candidates a JOIN corners c ON c.id = a.corner_id
    LEFT JOIN boundaries b ON b.corner_id = a.corner_id
    WHERE b.seq IS NULL OR a.seq < b.seq OR (a.seq = b.seq AND b.pre_stop IS NULL)
), outcomes AS (
    SELECT corner_id,
        list(id ORDER BY action_seq) AS chain_event_ids,
        coalesce(list(id ORDER BY action_seq) FILTER (WHERE attacking_shot), []::VARCHAR[]) AS shot_event_ids,
        count(*) FILTER (WHERE attacking_shot) AS shot_count,
        count(*) FILTER (WHERE attacking_shot AND is_goal) AS goal_count,
        coalesce(sum(xg ORDER BY action_seq) FILTER (WHERE attacking_shot), 0) AS provider_xg_sum
    FROM included GROUP BY corner_id
)
SELECT CAST($match_id AS BIGINT) AS match_id, c.id AS corner_event_id, c.team_id,
    CASE WHEN json_exists(c.payload, '$.team.name') THEN json_extract_string(c.payload, '$.team.name') ELSE 'Unknown' END AS team,
    CASE WHEN json_exists(c.payload, '$.player.name') THEN json_extract_string(c.payload, '$.player.name') ELSE 'Unknown' END AS taker,
    c.period, c.timestamp,
    CAST(json_extract_string(c.payload, '$.minute') AS BIGINT) AS minute,
    CAST(json_extract_string(c.payload, '$.second') AS BIGINT) AS second,
    CASE WHEN c.possession IS NULL THEN error('Corner has no possession identifier.') ELSE c.possession END AS possession_id,
    c.kind AS corner_kind,
    CASE WHEN json_exists(c.details, '$.technique.name') THEN json_extract_string(c.details, '$.technique.name') ELSE 'Unknown' END AS technique,
    CASE WHEN json_exists(c.details, '$.body_part.name') THEN json_extract_string(c.details, '$.body_part.name') ELSE 'Unknown' END AS foot,
    CASE WHEN json_exists(c.details, '$.height.name') THEN json_extract_string(c.details, '$.height.name') ELSE 'Unknown' END AS height,
    CASE WHEN c.kind = 'Shot' THEN 'direct_shot'
         WHEN json_extract_string(c.details, '$.height.name') = 'Ground Pass'
              AND isfinite(c.start_x) AND isfinite(c.start_y) AND isfinite(c.end_x) AND isfinite(c.end_y)
              AND sqrt(pow(c.end_x-c.start_x, 2) + pow(c.end_y-c.start_y, 2)) <= $short_limit THEN 'short'
         WHEN json_extract_string(c.details, '$.technique.name') IN ('Inswinging', 'Outswinging', 'Straight')
              THEN lower(json_extract_string(c.details, '$.technique.name'))
         ELSE 'unknown' END AS delivery_category,
    c.start_x, c.start_y, c.end_x, c.end_y,
    o.shot_count, o.goal_count, o.shot_count > 0 AS led_to_shot, o.provider_xg_sum,
    o.shot_event_ids, o.chain_event_ids,
    coalesce(c.starter_stop, b.reason, 'end_of_data') AS stop_reason,
    CAST($window_seconds AS DOUBLE) AS window_seconds, CAST($short_limit AS DOUBLE) AS short_limit
FROM corners c JOIN outcomes o ON o.corner_id = c.id
LEFT JOIN boundaries b ON b.corner_id = c.id
ORDER BY c.seq;
