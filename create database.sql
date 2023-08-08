CREATE DATABASE words_stats_telegram_bot;
USE words_stats_telegram_bot;

CREATE TABLE Settings(
    ChatID BIGINT,
    IgnoreTextFromPhoto BIT,
    IgnoreTextFromVideo BIT,
    IgnoreTextFromDocument BIT,
    IgnoreGif BIT,
    IgnoreStickers BIT,
    IgnoreChannelPosts BIT,
    ShowNames BIT,
    PRIMARY KEY (ChatID)
);

CREATE TABLE Users(
    UserID BIGINT,
    Nickname VARCHAR(32) UNIQUE,
    FirstName VARCHAR(64),
    PRIMARY KEY (UserID)
);

CREATE TABLE Words(
    WordID BIGINT NOT NULL,
    Word VARCHAR(100),
    PRIMARY KEY (WordID)
);

CREATE TABLE Messages(
    MessageID BIGINT,
    Date DATETIME,
    ChatID BIGINT,
    UserID BIGINT,
    PRIMARY KEY (MessageID),
    FOREIGN KEY (UserID) REFERENCES Users(UserID)
);

CREATE TABLE Messages_Words(
    MessageID BIGINT,
    WordID BIGINT,
    FOREIGN KEY (MessageID) REFERENCES Messages(MessageID) ON DELETE CASCADE,
    FOREIGN KEY (WordID) REFERENCES Words(WordID) ON DELETE CASCADE
);

CREATE TABLE Gifs(
	GifUniqueID VARCHAR(20),
    MessageID BIGINT,
    GifID VARCHAR(100),
    Duration INT,
    Height INT,
    Width INT,
    PRIMARY KEY(GifUniqueID, MessageID),
    FOREIGN KEY (MessageID) REFERENCES Messages(MessageID) ON DELETE CASCADE
);

CREATE TABLE Stickers(
	StickerUniqueID VARCHAR(20),
    MessageID BIGINT,
    StickerSetName VARCHAR(65),
    PRIMARY KEY(StickerUniqueID, MessageID),
    FOREIGN KEY (MessageID) REFERENCES Messages(MessageID) ON DELETE CASCADE
);
