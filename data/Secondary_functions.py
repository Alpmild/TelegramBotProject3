from data.Consts import TRANSCRIPTION


def transcription_title_into_english(name: str):
    """Перевод русских слов на английскую транскрипцию для удобного хранения"""
    name = name.strip()
    eng_name = ''

    for i in name:
        if i.lower() in TRANSCRIPTION:
            eng_name += TRANSCRIPTION[i.lower()].capitalize() if i.isupper() else TRANSCRIPTION[i]
        else:
            eng_name += ' '
    eng_name = eng_name.strip()
    eng_name = ''.join(map(lambda x: x.capitalize(), eng_name.split()))

    return eng_name


def get_token(path: str):
    """Получение токена"""
    with open(path, 'r') as token_file:
        return token_file.readline()


def normalized_text(text: str):
    """Нормализация текста, т.е. перевод в нижний регистр и удаление знаков препинания используется для поиска"""
    return ''.join([i.lower() for i in text if i.isalpha()])