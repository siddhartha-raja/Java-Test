package com.example;

public class App {
    public static void main(String[] args) {
        System.out.println(greet("GitHub Actions"));
    }

    public static String greet(String name) {
        return "Hello, " + name;
    }
}