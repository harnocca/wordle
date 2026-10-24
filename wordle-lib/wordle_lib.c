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

static char ascii_lower(char c)
{
    if (c >= 'A' && c <= 'Z')
        return c + ('a' - 'A');

    return c;
}

static bool get_ascii_word(PyObject *obj, const char **out, const char *name)
{
    if (!PyUnicode_Check(obj))
    {
        PyErr_Format(PyExc_TypeError, "%s must be a string", name);
        return false;
    }

    Py_ssize_t length = PyUnicode_GetLength(obj);

    if (length < 0)
        return false;

    if (length != WORD_LENGTH)
    {
        PyErr_Format(PyExc_ValueError, "%s must contain exactly %d ASCII letters", name, WORD_LENGTH);
        return false;
    }

    for (Py_ssize_t i = 0; i < length; i++)
    {
        Py_UCS4 ch = PyUnicode_ReadChar(obj, i);

        if (PyErr_Occurred())
            return false;

        bool is_letter = (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z');

        if (!is_letter)
        {
            PyErr_Format(PyExc_ValueError, "%s must contain only ASCII letters", name);
            return false;
        }
    }

    *out = PyUnicode_AsUTF8(obj);

    return *out != NULL;
}

static bool parse_strlist(const char **array, Py_ssize_t size, PyObject *pylist, const char *name)
{
    for (Py_ssize_t i = 0; i < size; i++)
    {
        PyObject *item = PyList_GetItem(pylist, i);

        if (item == NULL)
            return false;

        if (!get_ascii_word(item, &array[i], name))
            return false;
    }

    return true;
}

/*
 * Match a guess against a possible answer.
 *     0 = WRONG
 *     1 = POS
 *     2 = CORRECT
 */
static void match_board(const char *guess, const char *word, int board[WORD_LENGTH])
{
    char remaining[WORD_LENGTH];

    for (int i = 0; i < WORD_LENGTH; i++)
    {
        board[i] = WRONG;
        remaining[i] = ascii_lower(word[i]);
    }

    /* Exact matches */
    for (int i = 0; i < WORD_LENGTH; i++)
    {
        if (remaining[i] == ascii_lower(guess[i]))
        {
            board[i] = CORRECT;
            remaining[i] = '\0';
        }
    }

    /* Misplaced matches */
    for (int i = 0; i < WORD_LENGTH; i++)
    {
        if (remaining[i] == '\0')
            continue;

        for (int j = 0; j < WORD_LENGTH; j++)
        {
            if (board[j] == WRONG && remaining[i] == ascii_lower(guess[j]))
            {
                board[j] = POS;
                remaining[i] = '\0';
                break;
            }
        }
    }
}

/* Sums the board */
static int board_score(const int board[WORD_LENGTH])
{
    int score = 0;

    for (int i = 0; i < WORD_LENGTH; i++)
        score += board[i];

    return score;
}

/* Encodes the board into a base-3 integer */
static int encode_board(const int board[WORD_LENGTH])
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

            points += board_score(board);
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

    const char *guess = NULL;
    const char *word = NULL;

    if (!get_ascii_word(guess_obj, &guess, "guess"))
        return NULL;

    if (!get_ascii_word(word_obj, &word, "word"))
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

/* Shared wrapper for calc_entropy() and calc_points() */
static PyObject *method_calc_wrapper(PyObject *self, PyObject *args, CalcFunc calc_func)
{
    PyObject *g_obj = NULL;
    PyObject *w_obj = NULL;

    const char **guesses = NULL;
    const char **words = NULL;
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

    words = PyMem_Malloc((size_t)w_size * sizeof(*words));

    if (words == NULL)
    {
        PyErr_NoMemory();
        goto error;
    }

    if (g_size > 0)
    {
        guesses = PyMem_Malloc((size_t)g_size * sizeof(*guesses));
        entries = PyMem_Malloc((size_t)g_size * sizeof(*entries));

        if (guesses == NULL || entries == NULL)
        {
            PyErr_NoMemory();
            goto error;
        }
    }

    if (!parse_strlist(guesses, g_size, g_obj, "each guess"))
    {
        goto error;
    }

    if (!parse_strlist(words, w_size, w_obj, "each possible answer"))
    {
        goto error;
    }

    calc_func(guesses, g_size, words, w_size, entries);

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

    PyMem_Free(guesses);
    PyMem_Free(words);
    PyMem_Free(entries);

    return dict;

error:
    Py_XDECREF(dict);
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
