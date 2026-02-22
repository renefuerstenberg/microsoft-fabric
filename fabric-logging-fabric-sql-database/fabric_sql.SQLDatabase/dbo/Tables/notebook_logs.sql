CREATE TABLE [dbo].[notebook_logs] (
    [id]            BIGINT         IDENTITY (1, 1) NOT NULL,
    [log_timestamp] DATETIME2 (3)  NOT NULL,
    [log_level]     VARCHAR (20)   NOT NULL,
    [custom_run_id] VARCHAR (50)   NOT NULL,
    [notebook_name] VARCHAR (200)  NULL,
    [message]       NVARCHAR (MAX) NULL,
    PRIMARY KEY CLUSTERED ([id] ASC)
);


GO

