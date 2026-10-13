public.tbl_signs
  id        bigint       NOT NULL PRIMARY KEY
  sign_id   smallint     NOT NULL UNIQUE CHECK (sign_id BETWEEN 1 AND 12)
  sign_name varchar      NOT NULL

public.tbl_secondary_progression_forecasts
  id          bigint     NOT NULL PRIMARY KEY
  sign_id     smallint   NULL CHECK (sign_id BETWEEN 1 AND 12)
  degree      smallint   NULL CHECK (degree BETWEEN 0 AND 29)
  forecast_id integer    NULL

public.tbl_secondary_progression_forecasts_texts
  forecast_id   integer  NOT NULL PRIMARY KEY
  forecast_text text     NULL

public.tbl_tertiary1_forecasts
  id          bigint     NOT NULL PRIMARY KEY
  sign_id     smallint   NOT NULL CHECK (sign_id BETWEEN 1 AND 12)
  degree      smallint   NOT NULL CHECK (degree BETWEEN 0 AND 29)
  forecast_id integer    NOT NULL

public.tbl_tertiary1_forecasts_texts
  forecast_id   integer  NOT NULL PRIMARY KEY
  forecast_text text     NOT NULL

public.tbl_tertiary2_forecasts
  id          bigint     NOT NULL PRIMARY KEY
  sign_id     smallint   NOT NULL CHECK (sign_id BETWEEN 1 AND 12)
  tertiary    smallint   NOT NULL CHECK (tertiary BETWEEN 1 AND 3)
  degree      smallint   NOT NULL CHECK (degree BETWEEN 0 AND 29)
  forecast_id integer    NOT NULL

public.tbl_tertiary2_forecasts_texts
  forecast_id   integer  NOT NULL PRIMARY KEY
  forecast_text text     NOT NULL

public.tbl_moon_of_transit_daily_forecasts
  id             bigint  NOT NULL PRIMARY KEY
  moon_location  integer NOT NULL CHECK (moon_location BETWEEN 1 AND 12)
  forecast_group integer NOT NULL CHECK (forecast_group BETWEEN 1 AND 10)
  forecast_id    integer NOT NULL UNIQUE

public.tbl_moon_of_transit_daily_forecasts_texts
  forecast_id   integer  NOT NULL PRIMARY KEY
  forecast_text text     NULL