import os
import re
from googletrans import Translator

translator = Translator()

def get_directory():
    while True:
        path = input("Введите путь к папке (или нажмите Enter для текущей папки): ").strip()
        if not path:
            return os.getcwd()
        if os.path.isdir(path):
            return os.path.abspath(path)
        print("⨯ Ошибка: Указанной директории не существует!")

def list_yml_files(directory, page=1, per_page=10):
    try:
        files = [f for f in os.listdir(directory) if f.endswith(('.yml', '.yaml'))]
    except PermissionError:
        print("⨯ Ошибка: Нет доступа к указанной директории!")
        return [], 0
        
    total_pages = (len(files) + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    current_files = files[start:end]
    print(f"\nСтраница {page}/{total_pages}")
    for idx, fname in enumerate(current_files, 1):
        print(f"{idx}. {fname}")
    return current_files, total_pages

def select_file(directory):
    page = 1
    while True:
        current_files, total_pages = list_yml_files(directory, page)
        if not current_files:
            print("YAML файлы не найдены.")
            return None
        command = input("Введите номер файла, 'n' — след. страница, 'p' — пред. страница, 'q' — выход: ").strip().lower()
        if command == 'q':
            return None
        elif command == 'n':
            if page < total_pages:
                page += 1
            else:
                print("Это последняя страница.")
        elif command == 'p':
            if page > 1:
                page -= 1
            else:
                print("Это первая страница.")
        elif command.isdigit():
            num = int(command)
            if 1 <= num <= len(current_files):
                return os.path.join(directory, current_files[num - 1])
            else:
                print("Неверный номер.")
        else:
            print("Неверная команда.")

def get_target_filename(directory):
    while True:
        name = input("Введите имя конечного файла (без .yml): ").strip()
        if not name:
            print("Имя файла не может быть пустым.")
            continue
        if not name.endswith('.yml'):
            name += '.yml'
        return os.path.join(directory, name)

def parse_line(line):
    match = re.match(r'^(\s*)([\w_]+):\s*(["\'])(.*?)\3\s*$', line)
    if match:
        return (match.group(1), match.group(2), match.group(3), match.group(4))
    return None

def get_existing_translations(target_file):
    existing = {}
    if os.path.exists(target_file):
        with open(target_file, 'r', encoding='utf-8') as f:
            for line in f:
                parsed = parse_line(line)
                if parsed:
                    key = parsed[1]
                    existing[key] = line
    return existing

def split_special_segments(s):
    pattern = re.compile(
        r'(%[\w_]+%)'                   
        r'|(&[0-9a-fr])'                
        r'|(</?gradient>|</?rainbow>)'  
        r'|(<click:[^>]+>|</click>)'    
        r'|(\n)'                        
        r'|(<[^>]+>)',                  
        re.IGNORECASE
    )
    
    segments = []
    last_end = 0
    
    for match in pattern.finditer(s):
        start, end = match.span()
        if start > last_end:
            segments.append(('text', s[last_end:start]))
        
        for i, group in enumerate(match.groups()):
            if group:
                if i in (0,2,3,4,5):
                    segments.append(('raw', group))
                elif i == 1:
                    segments.append(('color', group))
                break
        
        last_end = end
    
    if last_end < len(s):
        segments.append(('text', s[last_end:]))
    
    return segments

def translate_segments(segments, dest_lang):
    translated = []
    for seg_type, seg_content in segments:
        if seg_type in ('raw', 'color'):
            translated.append(seg_content)
        else:
            try:
                result = translator.translate(seg_content, dest=dest_lang).text
                translated.append(result)
            except Exception as e:
                print(f"Ошибка перевода: {e}")
                translated.append(seg_content)
    return ''.join(translated)

def escape_value(value, quote):
    if quote == "'":
        return value.replace("'", "''")
    elif quote == '"':
        return value.replace('"', r'\"')
    return value

def process_file(original_path, target_path):  # <- Исправляем имя параметра
    existing = get_existing_translations(target_path)  # <- Меняем target_file на target_path
    temp_file = target_path + '.tmp'
    dest_lang = 'ru'

    with open(original_path, 'r', encoding='utf-8') as orig_f, \
         open(temp_file, 'w', encoding='utf-8') as temp_f:

        for line in orig_f:
            parsed = parse_line(line)
            if parsed:
                indent, key, quote, value = parsed
                if key in existing:
                    temp_f.write(existing[key])
                else:
                    segments = split_special_segments(value)
                    suggested = translate_segments(segments, dest_lang)
                    escaped_suggested = escape_value(suggested, quote)
                    print(f"\nОригинал: {line.strip()}")
                    print(f"Предложенный перевод: {key}: {quote}{escaped_suggested}{quote}")
                    
                    while True:
                        user_input = input("Введите перевод (=- принять, =-= оставить оригинал, =-=- сохранить и выйти): ").strip()
                        if user_input == '=-=-':
                            temp_f.close()
                            os.replace(temp_file, target_path)  # <- Исправляем здесь
                            return True
                        elif user_input == '=-':
                            new_val = suggested
                            break
                        elif user_input == '=-=':
                            new_val = value
                            break
                        else:
                            new_val = user_input
                            break
                            
                    if new_val is not None:
                        escaped_new = escape_value(new_val, quote)
                        new_line = f"{indent}{key}: {quote}{escaped_new}{quote}\n"
                        temp_f.write(new_line)
            else:
                temp_f.write(line)
                
    os.replace(temp_file, target_path)  # <- И здесь исправляем
    return False

def main():
    print("\n                     -=-=   YAML'ep   =-=-")
    directory = get_directory()
    original_path = select_file(directory)
    
    if not original_path:
        return
        
    target_path = get_target_filename(directory)
    process_exit = process_file(original_path, target_path)
    
    if process_exit:
        print("\nИзменения сохранены. Завершение работы.")
    else:
        print("\nПеревод завершён.")

if __name__ == "__main__":
    main()
