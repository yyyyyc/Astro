-- Table tbl_signs - contains all the signs

schema:

        create table public.tbl_signs (
        id bigserial not null,
        sign_id smallint not null,
        sign_name character varying(50) not null,
        constraint tblsigns_pkey primary key (id),
        constraint uq_tbl_signs_sign_id unique (sign_id),
        constraint tblsigns_sign_id_check check (
            (
            (sign_id >= 1)
            and (sign_id <= 12)
            )
        )
        ) TABLESPACE pg_default;

data:
INSERT INTO "public"."tbl_signs" ("id", "sign_id", "sign_name") VALUES (1, 1, 'Aries'), (2, 2, 'Taurus'), (3, 3, 'Gemini'), (4, 4, 'Cancer'), (5, 5, 'Leo'), (6, 6, 'Virgo'), (7, 7, 'Libra'), (8, 8, 'Scorpio'), (9, 9, 'Sagittarius'), (10, 10, 'Capricorn'), (11, 11, 'Aquarius'), (12, 12, 'Pisces');



-- Table tbl_tertiary1_forecasts - gets all tertiary I forecasts retrieved by   sign_id, and degree 

create table public.tbl_tertiary1_forecasts (
  id bigserial not null,
  sign_id smallint not null,
  degree smallint not null,
  forecast_id integer not null,
  constraint tbltertiary1texts_pkey primary key (id),
  constraint fk_tbl_tertiary1_forecasts_forecast foreign KEY (forecast_id) references tbl_tertiary1_forecasts_texts (forecast_id),
  constraint fk_tbl_tertiary1_forecasts_tbl_signs foreign KEY (sign_id) references tbl_signs (sign_id),
  constraint tbltertiary1texts_degree_check check (
    (
      (degree >= 0)
      and (degree <= 29)
    )
  ),
  constraint tbltertiary1texts_sign_id_check check (
    (
      (sign_id >= 1)
      and (sign_id <= 12)
    )
  )
) TABLESPACE pg_default;



-- Table tbl_tertiary1_forecasts_texts - contains all tertiary 1 forecasts texts and ids

create table public.tbl_tertiary1_forecasts_texts (
  forecast_id integer not null,
  forecast_text text not null,
  constraint pk_tbl_tertiary1_forecasts_texts primary key (forecast_id),
  constraint tbl_tertiary1_forecast_texts_forecast_id_key unique (forecast_id),
  constraint uq_tbl_tertiary1_forecast_texts_forecast_id unique (forecast_id)
) TABLESPACE pg_default;



-- Table tbl_tertiary2_forecasts - gets all tertiary 2 forecasts retrieved by   sign_id and tertiary (or sign_id and degree)  

create table public.tbl_tertiary2_forecasts (
  id bigserial not null,
  sign_id smallint not null,
  tertiary smallint not null,
  degree smallint not null,
  forecast_id integer not null,
  constraint tbltertiary2texts_pkey primary key (id),
  constraint fk_tbl_tertiary2_forecasts_forecast foreign KEY (forecast_id) references tbl_tertiary2_forecasts_texts (forecast_id),
  constraint fk_tbl_tertiary2_forecasts_tbl_signs foreign KEY (sign_id) references tbl_signs (sign_id),
  constraint tbltertiary2texts_degree_check check (
    (
      (degree >= 0)
      and (degree <= 29)
    )
  ),
  constraint tbltertiary2texts_sign_id_check check (
    (
      (sign_id >= 1)
      and (sign_id <= 12)
    )
  ),
  constraint tbltertiary2texts_tertiary_check check (
    (
      (tertiary >= 1)
      and (tertiary <= 3)
    )
  )
) TABLESPACE pg_default;



-- Table tbl_tertiary2_forecasts_texts - contains all tertiary 2 forecasts texts and ids
create table public.tbl_tertiary2_forecasts_texts (
  forecast_id integer not null,
  forecast_text text not null,
  constraint pk_tbl_tertiary2_forecasts_texts primary key (forecast_id),
  constraint tbl_tertiary2_forecast_texts_forecast_id_key unique (forecast_id),
  constraint uq_tbl_tertiary2_forecast_texts_forecast_id unique (forecast_id)
) TABLESPACE pg_default;

