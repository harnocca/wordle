#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <stdbool.h>
#include <string.h>

#define WRONG 0
#define POS 1
#define CORRECT 2

#define WORD_LENGTH 5
#define PATTERNS 243

typedef struct
{
    const char *word;
    double value;
} Entry;

typedef void (*CalcFunc)(const char **guesses, Py_ssize_t g_size, const char **words, Py_ssize_t w_size, Entry *result);

/*
 * Validate a Python string, copy it lowercased into `word`, and NUL-terminate.
 * `word` must hold at least WORD_LENGTH + 1 bytes.
 */
static bool get_ascii_word(PyObject *obj, char *word, const char *id)
{
    if (!PyUnicode_Check(obj))
    {
        PyErr_Format(PyExc_TypeError, "%s must be a string", id);
        return false;
    }

    Py_ssize_t length = PyUnicode_GetLength(obj);

    if (length < 0)
        return false;

    if (length != WORD_LENGTH)
    {
        PyErr_Format(PyExc_ValueError, "%s must contain exactly %d ASCII letters", id, WORD_LENGTH);
        return false;
    }

    for (Py_ssize_t i = 0; i < length; i++)
    {
        Py_UCS4 ch = PyUnicode_ReadChar(obj, i);

        if (PyErr_Occurred())
            return false;

        if (ch >= 'a' && ch <= 'z')
        {
            word[i] = (char)ch;
        }
        else if (ch >= 'A' && ch <= 'Z')
        {
            word[i] = (char)(ch + ('a' - 'A'));
        }
        else
        {
            PyErr_Format(PyExc_ValueError, "%s must contain only ASCII letters", id);
            return false;
        }
    }

    word[WORD_LENGTH] = '\0';
    return true;
}

/*
 * Parse a Python list of strings into a contiguous C buffer and an array of
 * pointers into that buffer. Both outputs are owned by the caller and must be
 * freed with PyMem_Free.
 */
static bool parse_strlist(Py_ssize_t size, PyObject *pylist, const char *id, const char ***words_ptr, char **head_ptr)
{
    *words_ptr = NULL;
    *head_ptr = NULL;

    if (size == 0)
        return true;

    char *head = PyMem_Malloc((size_t)size * (WORD_LENGTH + 1));

    if (head == NULL)
    {
        PyErr_NoMemory();
        return false;
    }

    const char **array = PyMem_Malloc((size_t)size * sizeof(const char *));

    if (array == NULL)
    {
        PyMem_Free(head);
        PyErr_NoMemory();
        return false;
    }

    for (Py_ssize_t i = 0; i < size; i++)
    {
        PyObject *item = PyList_GetItem(pylist, i);

        if (item == NULL)
            goto error;

        array[i] = head + i * (WORD_LENGTH + 1);

        if (!get_ascii_word(item, (char *)array[i], id))
            goto error;
    }

    *words_ptr = array;
    *head_ptr = head;
    return true;

error:
    PyMem_Free(head);
    PyMem_Free(array);
    return false;
}

/*
 * Match a guess against a possible answer.
 *     0 = WRONG
 *     1 = POS
 *     2 = CORRECT
 *
 * The count table caps misplaced (yellow) letters to the number of times the
 * letter actually appears in the answer after exact matches are consumed,
 * which matches Wordle's duplicate-letter rule.
 */
static void match_board(const char *guess, const char *word, int board[WORD_LENGTH])
{
    int counts[26] = {0};

    /* First pass: mark exact matches and count remaining answer letters. */
    for (int i = 0; i < WORD_LENGTH; i++)
    {
        if (guess[i] == word[i])
        {
            board[i] = CORRECT;
        }
        else
        {
            board[i] = WRONG;
            counts[word[i] - 'a']++;
        }
    }

    /* Second pass: assign yellows using the remaining letter counts. */
    for (int i = 0; i < WORD_LENGTH; i++)
    {
        if (board[i] == CORRECT)
            continue;

        int idx = guess[i] - 'a';

        if (counts[idx] > 0)
        {
            board[i] = POS;
            counts[idx]--;
        }
    }
}

/* Encodes the board into a base-3 integer. */
static inline int encode_board(const int board[WORD_LENGTH])
{
    int encoded = 0;
    int power = 1;

    for (int i = 0; i < WORD_LENGTH; i++)
    {
        encoded += board[i] * power;
        power *= 3;
    }

    return encoded;
}

/*
 * Calculate Shannon entropy for every guess.
 */
static void calc_entropy(const char **guesses, Py_ssize_t g_size, const char **words, Py_ssize_t w_size, Entry *result)
{
    for (Py_ssize_t i = 0; i < g_size; i++)
    {
        const char *guess = guesses[i];

        Py_ssize_t patterns[PATTERNS] = {0};
        double entropy = 0.0;

        for (Py_ssize_t j = 0; j < w_size; j++)
        {
            int board[WORD_LENGTH];

            match_board(guess, words[j], board);

            patterns[encode_board(board)]++;
        }

        for (int k = 0; k < PATTERNS; k++)
        {
            if (patterns[k] == 0)
                continue;

            double p = (double)patterns[k] / (double)w_size;

            entropy -= p * log2(p);
        }

        result[i] = (Entry){guess, entropy};
    }
}

/*
 * Sum the positional board scores across all possible answers.
 */
static void calc_points(const char **guesses, Py_ssize_t g_size, const char **words, Py_ssize_t w_size, Entry *result)
{
    for (Py_ssize_t i = 0; i < g_size; i++)
    {
        const char *guess = guesses[i];
        double points = 0.0;

        for (Py_ssize_t j = 0; j < w_size; j++)
        {
            int board[WORD_LENGTH];

            match_board(guess, words[j], board);

            for (int k = 0; k < WORD_LENGTH; k++)
                points += board[k];
        }

        result[i] = (Entry){guess, points};
    }
}

static PyObject *method_match(PyObject *self, PyObject *args)
{
    PyObject *guess_obj = NULL;
    PyObject *word_obj = NULL;

    if (!PyArg_ParseTuple(args, "OO", &guess_obj, &word_obj))
    {
        return NULL;
    }

    char guess[WORD_LENGTH + 1];
    char word[WORD_LENGTH + 1];

    if (!get_ascii_word(guess_obj, guess, "guess"))
        return NULL;

    if (!get_ascii_word(word_obj, word, "word"))
        return NULL;

    int board[WORD_LENGTH];

    match_board(guess, word, board);

    PyObject *tuple = PyTuple_New(WORD_LENGTH);

    if (tuple == NULL)
        return NULL;

    for (int i = 0; i < WORD_LENGTH; i++)
    {
        PyObject *value = PyLong_FromLong(board[i]);

        if (value == NULL)
        {
            Py_DECREF(tuple);
            return NULL;
        }

        /* The tuple takes ownership of value. */
        PyTuple_SET_ITEM(tuple, i, value);
    }

    return tuple;
}

/* Shared wrapper for calc_entropy() and calc_points(). */
static PyObject *method_calc_wrapper(PyObject *self, PyObject *args, CalcFunc calc_func)
{
    PyObject *g_obj = NULL;
    PyObject *w_obj = NULL;

    const char **guesses = NULL;
    const char **words = NULL;

    /* Backing buffers returned by parse_strlist; freed with the pointer arrays. */
    char *g_head = NULL;
    char *w_head = NULL;

    Entry *entries = NULL;
    PyObject *dict = NULL;

    if (!PyArg_ParseTuple(args, "OO", &g_obj, &w_obj))
        return NULL;

    if (!PyList_Check(g_obj) || !PyList_Check(w_obj))
    {
        PyErr_SetString(PyExc_TypeError, "guesses and words must be lists of strings");
        return NULL;
    }

    Py_ssize_t g_size = PyList_Size(g_obj);
    Py_ssize_t w_size = PyList_Size(w_obj);

    if (g_size < 0 || w_size < 0)
        return NULL;

    if (w_size == 0)
    {
        PyErr_SetString(PyExc_ValueError, "words must contain at least one possible answer");
        return NULL;
    }

    if (!parse_strlist(g_size, g_obj, "each guess", &guesses, &g_head))
        goto error;

    if (!parse_strlist(w_size, w_obj, "each possible answer", &words, &w_head))
        goto error;

    if (g_size > 0)
    {
        entries = PyMem_Malloc((size_t)g_size * sizeof(*entries));

        if (entries == NULL)
        {
            PyErr_NoMemory();
            goto error;
        }
    }

    calc_func(guesses, g_size, words, w_size, entries);

    /* Build the result dictionary from the computed entries. */
    dict = PyDict_New();

    if (dict == NULL)
        goto error;

    for (Py_ssize_t i = 0; i < g_size; i++)
    {
        PyObject *value = PyFloat_FromDouble(entries[i].value);

        if (value == NULL)
            goto error;

        if (PyDict_SetItemString(dict, entries[i].word, value) < 0)
        {
            Py_DECREF(value);
            goto error;
        }

        Py_DECREF(value);
    }

    PyMem_Free(g_head);
    PyMem_Free(w_head);
    PyMem_Free(guesses);
    PyMem_Free(words);
    PyMem_Free(entries);

    return dict;

error:
    Py_XDECREF(dict);
    PyMem_Free(g_head);
    PyMem_Free(w_head);
    PyMem_Free(guesses);
    PyMem_Free(words);
    PyMem_Free(entries);

    return NULL;
}

static PyObject *method_calc_entropy(PyObject *self, PyObject *args)
{
    return method_calc_wrapper(self, args, calc_entropy);
}

static PyObject *method_calc_points(PyObject *self, PyObject *args)
{
    return method_calc_wrapper(self, args, calc_points);
}

static PyMethodDef KWordleLibMethods[] = {
    {.ml_name = "match", .ml_meth = method_match, .ml_flags = METH_VARARGS},
    {.ml_name = "calc_entropy", .ml_meth = method_calc_entropy, .ml_flags = METH_VARARGS},
    {.ml_name = "calc_points", .ml_meth = method_calc_points, .ml_flags = METH_VARARGS},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef wordle_lib_module = {PyModuleDef_HEAD_INIT, "_wordle_lib",
                                               "Internal C implementation for wordle_lib.", -1, KWordleLibMethods};

PyMODINIT_FUNC PyInit__wordle_lib(void)
{
    return PyModule_Create(&wordle_lib_module);
}
