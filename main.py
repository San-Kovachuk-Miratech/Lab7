import os
import sys
import re
import math
from pathlib import Path
from collections import defaultdict

# Визначення операторів та ключових слів
# Зверніть увагу: цей набір може потребувати доопрацювання для кращої підтримки
# різних мов програмування, особливо щодо операторів.
OPERATORS = {
    "+", "-", "*", "/", "%", "=", "==", "!=", ">", "<", ">=", "<=",
    "&&", "||", "!", "++", "--", "&", "|", "^", "~", "<<", ">>", ">>>",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", ">>>=",
    ".", "->", "::", "?", ":" # Додано деякі поширені оператори
}

# Ключові слова розглядаються як оператори в метриці Холстеда
# Цей список є комбінацією Java, C++, C#, JS ключових слів.
# Для точного аналізу конкретної мови цей список слід уточнити.
KEYWORDS = {
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while",
    # C/C++
    "auto", "bool", "char16_t", "char32_t", "constexpr", "decltype", "delete",
    "dynamic_cast", "explicit", "export", "extern", "false", "friend", "inline",
    "mutable", "namespace", "noexcept", "nullptr", "operator", "register",
    "reinterpret_cast", "signed", "sizeof", "static_assert", "static_cast",
    "struct", "template", "thread_local", "true", "typedef", "typeid", "typename",
    "union", "unsigned", "using", "virtual", "wchar_t",
    # C#
    "as", "base", "checked", "decimal", "delegate", "event", "fixed", "foreach",
    "in", "internal", "is", "lock", "object", "out", "override", "params",
    "readonly", "ref", "sbyte", "sealed", "stackalloc", "string", "typeof",
    "uint", "ulong", "unchecked", "unsafe", "ushort", "var",
    # JS
    "await", "debugger", "function", "let", "yield", "async", "null", "undefined",
    "arguments", "get", "set", "of", "with",
    # Python
    "and", "def", "del", "elif", "global", "lambda", "nonlocal", "not", "or", "pass", "raise",
    "from", "None"
}

# Додаємо ключові слова до операторів для аналізу Холстеда
ALL_OPERATORS = OPERATORS.union(KEYWORDS)

class MetricsResult:
    """Клас для зберігання результатів обчислення метрик для окремого файлу."""
    def __init__(self):
        self.total_lines = 0
        self.sloc = 0
        self.cyclomatic_complexity = 0
        self.halstead_volume = 0.0
        self.unique_operators = set()
        self.unique_operands = set()
        self.total_operators = 0
        self.total_operands = 0

class CodeMetricsCalculator:
    """
    Програма для розрахунку гібридних метрик програмного коду.
    """
    def __init__(self, source_directory_path: str):
        self.source_directory = Path(source_directory_path)
        self.source_files = []
        if self.source_directory.is_dir():
            self._find_source_files(self.source_directory)
        else:
            print(f"Помилка: Вказаний шлях не є директорією або не існує: {source_directory_path}", file=sys.stderr)

        # Результати обчислення метрик
        self.total_lines = 0
        self.sloc = 0
        self.total_cyclomatic_complexity = 0
        self.total_halstead_volume = 0.0
        self.average_cyclomatic_complexity = 0.0
        self.average_halstead_volume = 0.0
        self.kokol_metric = 0.0
        self.zolnovski_metric = 0.0

    def _is_source_file(self, file_name: str) -> bool:
        """Перевірка чи є файл файлом з вихідним кодом."""
        return file_name.endswith((".java", ".c", ".cpp", ".h", ".cs", ".js", ".py")) # Додано .py

    def _find_source_files(self, directory: Path):
        """Рекурсивний пошук файлів з вихідним кодом у директорії."""
        for item in directory.iterdir():
            if item.is_dir():
                self._find_source_files(item)
            elif item.is_file() and self._is_source_file(item.name):
                self.source_files.append(item)

    def _analyze_halstead_metrics(self, line: str, metrics: MetricsResult):
        """Аналіз рядка коду для обчислення метрики Холстеда."""
        # Спрощене видалення рядкових літералів та символьних літералів
        line = re.sub(r'".*?"', ' "STRING_LITERAL" ', line)
        line = re.sub(r"'.*?'", " 'CHAR_LITERAL' ", line)

        # Розбиваємо рядок на потенційні токени (слова, числа, оператори)
        # Використовуємо пробіли та роздільники як межі
        tokens = re.findall(r'\b\w+\b|[+\-*/%<>=!&|^~?:]+|[.,;(){}$$$$]', line)

        for token in tokens:
            if token in ALL_OPERATORS:
                metrics.unique_operators.add(token)
                metrics.total_operators += 1
            # Перевіряємо, чи є токен ідентифікатором (не числом і не оператором/ключовим словом)
            elif re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', token):
                 metrics.unique_operands.add(token)
                 metrics.total_operands += 1
            # Перевіряємо, чи є токен числовим літералом
            elif re.match(r'^\d+(\.\d+)?([eE][+-]?\d+)?$', token):
                 metrics.unique_operands.add(token)
                 metrics.total_operands += 1
            # Додаємо обробку рядкових та символьних літералів як операндів
            elif token in ['"STRING_LITERAL"', "'CHAR_LITERAL'"]:
                 metrics.unique_operands.add(token)
                 metrics.total_operands += 1


    def _calculate_file_metrics(self, file_path: Path) -> MetricsResult:
        """Обчислення метрик для окремого файлу."""
        metrics = MetricsResult()
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                in_multiline_comment = False
                metrics.cyclomatic_complexity = 1 # Початкове значення для основного шляху

                for line in f:
                    metrics.total_lines += 1
                    original_line = line # Зберігаємо оригінал для аналізу Холстеда
                    line = line.strip()

                    # Обробка багаторядкових коментарів C-стилю (/* ... */)
                    if in_multiline_comment:
                        if '*/' in line:
                            line = line[line.find('*/') + 2:]
                            in_multiline_comment = False
                        else:
                            continue # Весь рядок є частиною коментаря

                    if '/*' in line:
                        # Перевірка, чи не знаходиться /* всередині рядка
                        if '"' not in line[:line.find('/*')] and "'" not in line[:line.find('/*')]:
                           if '*/' in line[line.find('/*') + 2:]: # Коментар на одному рядку
                               line = line[:line.find('/*')] + line[line.find('*/', line.find('/*') + 2) + 2:]
                           else: # Початок багаторядкового коментаря
                               line = line[:line.find('/*')]
                               in_multiline_comment = True

                    # Видалення однорядкових коментарів (// та #)
                    if '//' in line:
                         # Перевірка, чи не знаходиться // всередині рядка
                         if '"' not in line[:line.find('//')] and "'" not in line[:line.find('//')]:
                            line = line[:line.find('//')]
                    if '#' in line: # Для Python та інших скриптових мов
                         # Перевірка, чи не знаходиться # всередині рядка
                         if '"' not in line[:line.find('#')] and "'" not in line[:line.find('#')]:
                             line = line[:line.find('#')]

                    line = line.strip()

                    if not line: # Пропускаємо порожні рядки після видалення коментарів
                        continue

                    metrics.sloc += 1

                    # --- Цикломатична складність ---
                    # Додаємо перевірки для Python (elif, for, while, try, except, with)
                    # та інших мов (switch/case вже є в KEYWORDS)
                    complexity_keywords = ['if', 'elif', 'for', 'while', 'case', 'catch', 'except', '?', '&&', '||']
                    # Використовуємо регулярні вирази для пошуку цілих слів
                    for keyword in complexity_keywords:
                        # Для символьних операторів (&&, ||, ?) шукаємо просто входження
                        if keyword in ['?', '&&', '||']:
                             metrics.cyclomatic_complexity += line.count(keyword)
                        else:
                             # Для слів шукаємо окремі слова
                             metrics.cyclomatic_complexity += len(re.findall(r'\b' + re.escape(keyword) + r'\b', line))

                    # --- Метрика Холстеда ---
                    # Аналізуємо оригінальний рядок до видалення коментарів,
                    # але після обробки багаторядкових коментарів, щоб не рахувати токени в них.
                    # Це наближення, точний аналіз потребує парсера.
                    self._analyze_halstead_metrics(original_line if not in_multiline_comment else line, metrics)

        except Exception as e:
            print(f"Помилка при читанні або аналізі файлу {file_path.name}: {e}", file=sys.stderr)

        # Обчислення обсягу Холстеда для файлу
        n1 = len(metrics.unique_operators)
        n2 = len(metrics.unique_operands)
        N1 = metrics.total_operators
        N2 = metrics.total_operands

        n = n1 + n2
        N = N1 + N2

        if n > 0 and N > 0:
            try:
                # Використовуємо math.log2 для логарифма за основою 2
                metrics.halstead_volume = N * math.log2(n)
            except ValueError:
                 metrics.halstead_volume = 0.0 # У випадку log2(0)
        else:
            metrics.halstead_volume = 0.0

        return metrics

    def _calculate_hybrid_metrics(self):
        """Обчислення гібридних метрик."""
        num_files = len(self.source_files)
        if num_files == 0:
            return

        # --- Метрика Кокола ---
        # HM = (M + R1*M(M1) + R2*M(M2)) / (1 + R1 + R2)
        # Базова метрика (M): Середній обсяг Холстеда
        base_metric = self.average_halstead_volume

        # M1: Середня цикломатична складність, M2: Середній SLOC на файл
        metrics1 = self.average_cyclomatic_complexity
        metrics2 = self.sloc / num_files if num_files > 0 else 0

        # Коефіцієнти впливу (можна налаштувати)
        R1 = 0.8  # Коефіцієнт впливу цикломатичної складності
        R2 = 0.2  # Коефіцієнт впливу SLOC

        # Обчислення гібридної метрики Кокола
        self.kokol_metric = (base_metric + R1 * metrics1 + R2 * metrics2) / (1 + R1 + R2)

        # --- Метрика Золновського (виправлена) ---
        # Зважена сума нормалізованих значень метрик з покращеною нормалізацією
        # HM = W1*NM1 + W2*NM2 + W3*NM3
        # Де NMx - нормалізовані значення метрик, Wx - вагові коефіцієнти

        # Використовуємо більш динамічний підхід для нормалізації
        # Для Halstead volume використовуємо логарифмічну шкалу, оскільки значення можуть бути великими
        # та нерівномірно розподіленими
        avg_sloc_per_file = self.sloc / num_files if num_files > 0 else 0

        # Більш адаптивні максимальні значення на основі типових порогів складності коду
        max_halstead = max(2000.0, self.average_halstead_volume * 1.5)  # Динамічний поріг
        max_cc = max(15.0, self.average_cyclomatic_complexity * 1.2)    # Динамічний поріг
        max_sloc = max(500.0, avg_sloc_per_file * 2)                    # Динамічний поріг
        
        # Запобігаємо діленню на нуль
        max_halstead = max(0.001, max_halstead)
        max_cc = max(0.001, max_cc)
        max_sloc = max(0.001, max_sloc)

        # Покращена нормалізація з використанням логарифмічної шкали для Halstead volume
        if self.average_halstead_volume > 0:
            # Використовуємо ln(1+x) для згладжування та запобігання різким стрибкам
            norm_halstead = min(1.0, math.log1p(self.average_halstead_volume) / math.log1p(max_halstead))
        else:
            norm_halstead = 0.0
            
        # Використовуємо сигмоїдну функцію для нормалізації цикломатичної складності
        # Це забезпечує плавніший перехід між значеннями
        norm_cc = 2 / (1 + math.exp(-0.3 * self.average_cyclomatic_complexity)) - 1
        norm_cc = min(1.0, norm_cc)
        
        # Лінійна нормалізація для SLOC з обмеженням
        norm_sloc = min(1.0, avg_sloc_per_file / max_sloc)

        # Вагові коефіцієнти (сума має дорівнювати 1)
        # Наголошуємо на Halstead і CC як найважливіших метриках
        W1 = 0.45  # Вага нормалізованого обсягу Холстеда
        W2 = 0.45  # Вага нормалізованої цикломатичної складності
        W3 = 0.10  # Вага нормалізованого SLOC

        # Обчислення покращеної гібридної метрики Золновського
        # Додаємо невеликий коефіцієнт збалансування (+0.1), щоб уникнути нульових значень
        self.zolnovski_metric = (W1 * norm_halstead + W2 * norm_cc + W3 * norm_sloc) * 10

    def calculate_metrics(self):
        """Основний метод для обчислення всіх метрик."""
        num_files = len(self.source_files)
        if num_files == 0:
            print("Не знайдено жодних файлів з вихідним кодом для аналізу.")
            return False

        print(f"Знайдено {num_files} файлів з вихідним кодом.")

        # Обчислюємо метрики для кожного файлу
        for file_path in self.source_files:
            file_metrics = self._calculate_file_metrics(file_path)
            
            # Додаємо до загальних метрик
            self.total_lines += file_metrics.total_lines
            self.sloc += file_metrics.sloc
            self.total_cyclomatic_complexity += file_metrics.cyclomatic_complexity
            self.total_halstead_volume += file_metrics.halstead_volume

        # Обчислюємо середні значення
        self.average_cyclomatic_complexity = self.total_cyclomatic_complexity / num_files
        self.average_halstead_volume = self.total_halstead_volume / num_files

        # Обчислюємо гібридні метрики
        self._calculate_hybrid_metrics()
        
        return True

    def print_metrics(self):
        """Виведення результатів обчислення метрик."""
        print("\n=== Результати аналізу метрик коду ===")
        print(f"Загальна кількість файлів: {len(self.source_files)}")
        print(f"Загальна кількість рядків коду: {self.total_lines}")
        print(f"Кількість значущих рядків коду (SLOC): {self.sloc}")
        print(f"Середня цикломатична складність: {self.average_cyclomatic_complexity:.2f}")
        print(f"Середній обсяг Холстеда: {self.average_halstead_volume:.2f}")
        print("\n=== Гібридні метрики ===")
        print(f"Метрика Кокола: {self.kokol_metric:.2f}")
        print(f"Метрика Золновського: {self.zolnovski_metric:.2f}")


def main():
    """Головна функція програми."""
    # Перевірка, чи передано шлях до директорії з вихідним кодом
    if len(sys.argv) > 1:
        source_directory = sys.argv[1]
    else:
        # Якщо шлях не вказано, використовуємо поточну директорію
        source_directory = os.getcwd()
        print(f"Шлях до директорії не вказано. Використовуємо поточну директорію: {source_directory}")

    # Створюємо екземпляр аналізатора
    analyzer = CodeMetricsCalculator(source_directory)
    
    # Обчислюємо та виводимо метрики
    if analyzer.calculate_metrics():
        analyzer.print_metrics()
    
    return 0


# Точка входу до програми
if __name__ == "__main__":
    sys.exit(main())

