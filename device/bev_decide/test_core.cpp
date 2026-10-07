// test_core.cpp -- host driver for tests/test_bev_core.py. Not shipped to the board.
//
//   test_core layout < fields     token layout of one question, as JSON
//   test_core head <bin> <idx> <H> <D> <layers> <tasks> <eps> < numbers
//                                  decision-head probabilities, one per line
//
// layout input: length-prefixed fields ("<n>\n" then n bytes): state, type,
// instructions, max_state_tokens, max_choice_tokens, n_criteria, then key and
// value per criterion. The tokenizer is one token per byte (id = byte + 1000),
// the same toy tokenizer the Python side gives bev's own encode.py.
// head input (whitespace separated): task_type C, then C*H choice values, then
// H answer values. idx lines: name offset nbytes d0 [d1].

#include "bev_core.hpp"

#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>

static std::string field(std::istream & in) {
    std::string line;
    if (!std::getline(in, line)) throw std::runtime_error("missing field");
    std::string s((size_t) std::stoul(line), '\0');
    in.read(&s[0], (std::streamsize) s.size());
    return s;
}

static bev::Tokens tok(const std::string & s) {
    bev::Tokens t;
    for (unsigned char ch : s) t.push_back(1000 + ch);
    return t;
}

static std::string detok(const bev::Tokens & t) {
    std::string s;
    for (int32_t id : t) s.push_back((char) (id - 1000));
    return s;
}

static void ints(std::ostream & o, const bev::Tokens & t) {
    o << "[";
    for (size_t i = 0; i < t.size(); ++i) o << (i ? "," : "") << t[i];
    o << "]";
}

static int layout() {
    bev::EncodingConsts c;
    c.task_prompts = {{"choice", "Choose the best option."}, {"score", "Rate it on the given scale."},
                      {"noul", "Answer yes or no."}};
    c.task_types = {{"choice", 0}, {"noul", 1}, {"score", 2}};
    std::string state = field(std::cin);
    bev::Question q;
    q.type = field(std::cin);
    q.instructions = field(std::cin);
    c.max_state_tokens = std::stoi(field(std::cin));
    c.max_choice_tokens = std::stoi(field(std::cin));
    int n = std::stoi(field(std::cin));
    for (int i = 0; i < n; ++i) {
        std::string k = field(std::cin);
        q.criteria.emplace_back(k, field(std::cin));
    }
    bev::Layout L = bev::encode(state, q, c, tok, detok);
    std::ostream & o = std::cout;
    o << "{\"prompt\":";
    ints(o, L.prompt);
    o << ",\"options\":[";
    for (size_t i = 0; i < L.options.size(); ++i) { o << (i ? "," : ""); ints(o, L.options[i]); }
    o << "],\"read_idx\":[";
    for (size_t i = 0; i < L.read_idx.size(); ++i) o << (i ? "," : "") << L.read_idx[i];
    o << "],\"answer\":";
    ints(o, L.answer);
    o << ",\"keys\":[";
    for (size_t i = 0; i < L.keys.size(); ++i) o << (i ? "," : "") << "\"" << L.keys[i] << "\"";
    o << "],\"task_type\":" << L.task_type << ",\"answer_pos0\":" << L.answer_pos0()
      << ",\"n_tokens\":" << L.n_tokens() << "}\n";
    return 0;
}

static int head(char ** argv) {
    std::ifstream bf(argv[2], std::ios::binary);
    std::vector<char> raw((std::istreambuf_iterator<char>(bf)), std::istreambuf_iterator<char>());
    std::vector<float> bin(raw.size() / 4);
    std::memcpy(bin.data(), raw.data(), bin.size() * 4);
    std::vector<bev::TensorSpec> specs;
    std::ifstream idx(argv[3]);
    std::string line;
    while (std::getline(idx, line)) {
        std::istringstream ls(line);
        bev::TensorSpec s;
        ls >> s.name >> s.offset >> s.nbytes;
        int64_t d;
        while (ls >> d) s.shape.push_back(d);
        if (!s.name.empty()) specs.push_back(s);
    }
    bev::Head h;
    h.load(bin, specs, std::stoi(argv[4]), std::stoi(argv[5]), std::stoi(argv[6]), std::stoi(argv[7]),
           std::stod(argv[8]));
    int task, C;
    std::cin >> task >> C;
    std::vector<std::vector<float>> choices(C, std::vector<float>(h.H));
    for (auto & r : choices)
        for (auto & z : r) std::cin >> z;
    std::vector<float> ans(h.H);
    for (auto & z : ans) std::cin >> z;
    std::cout.precision(17);
    for (double p : h.forward(choices, ans, task)) std::cout << p << "\n";
    return 0;
}

int main(int argc, char ** argv) {
    try {
        if (argc >= 2 && std::string(argv[1]) == "layout") return layout();
        if (argc == 9 && std::string(argv[1]) == "head") return head(argv);
        std::cerr << "usage: test_core layout | head <bin> <idx> <H> <D> <layers> <tasks> <eps>\n";
        return 2;
    } catch (const std::exception & e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
}
