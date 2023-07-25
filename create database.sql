CREATE DATABASE words_stats_telegram_bot;
USE words_stats_telegram_bot;

CREATE TABLE Settings(
    ChatID BIGINT NOT NULL,
    IgnoreTextFromPhoto BIT,
    IgnoreTextFromVideo BIT,
    IgnoreGif BIT,
    IgnoreStickers BIT,
    IgnoreChannelPosts BIT,
    PRIMARY KEY (ChatID)
);

CREATE TABLE Users(
    UserID BIGINT NOT NULL,
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
    MessageID BIGINT NOT NULL AUTO_INCREMENT,
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
    GifID VARCHAR(50),
    MessageID BIGINT,
    PRIMARY KEY(GifUniqueID, GifID),
    FOREIGN KEY (MessageID) REFERENCES Messages(MessageID) ON DELETE CASCADE
);

CREATE TABLE Stickers(
	StickerUniqueID VARCHAR(20),
    StickerID VARCHAR(50),
    MessageID BIGINT,
    PRIMARY KEY(StickerUniqueID, StickerID),
    FOREIGN KEY (MessageID) REFERENCES Messages(MessageID) ON DELETE CASCADE
);



INSERT IGNORE INTO Settings (ChatID, AddBotsMessagesToUser, BotMessagesRegexps, ReadTextFromPhoto, ReadTextFromVideo, CountGif,CountStickers,IgnoreCommands,IgnoreChannelPosts) VALUE (0, 0, '', 1, 1, 1);
INSERT IGNORE INTO Users (UserID, Nickname, FirstName) VALUE (0, '@nickname', 'first name');
INSERT INTO Words (WordID, Word) VALUES (0, 'word') ON DUPLICATE KEY UPDATE WordID=WordID;
INSERT INTO Messages (Date, ChatID, UserID) VALUE ('01-01-2023', 0, 0);
INSERT INTO Messages_Words (MessageID, WordID) VALUES (0, 0);

SELECT AddBotsMessagesToUser,BotMessagesRegexps,IgnoreTextFromPhoto,IgnoreTextFromVideo,IgnoreGif,IgnoreStickers,IgnoreCommands,IgnoreChannelPosts FROM Settings WHERE ChatID=0;


INSERT INTO Words(WordID,Word)VALUES(-5710977158703794642,'hello') ON DUPLICATE KEY UPDATE WordID=WordID;